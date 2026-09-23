"""Test evaluation integrity and failure accounting without an AI or cluster."""

import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import evaluate_skills as evaluation


class EvaluationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.output = Path(self.temp.name) / "matrix"
        self.trials = evaluation.prepare(self.output, repeats=1)

    def test_paired_inputs_and_evaluator_separation(self):
        pairs = {}
        for name in self.trials:
            trial = self.output / name
            metadata = json.loads((trial / "trial.json").read_text())
            workspace = trial / "workspace"
            self.assertFalse((workspace / "review.json").exists())
            self.assertFalse((workspace / "cases.json").exists())
            self.assertEqual((workspace / "skill").exists(), metadata["arm"] == "skill")
            evidence = (workspace / "evidence.json").read_bytes()
            profile = (workspace / "profile.yaml").read_bytes()
            pairs.setdefault(metadata["case"], []).append((evidence, profile))
            prompt = (trial / "prompt.txt").read_text()
            self.assertNotIn("required_findings", prompt)
        self.assertEqual(len(pairs), 6)
        for pair in pairs.values():
            self.assertEqual(len(pair), 2)
            self.assertEqual(pair[0], pair[1])

    def test_no_overwrite_and_no_source_repository_output(self):
        with self.assertRaisesRegex(ValueError, "never overwritten"):
            evaluation.prepare(self.output)
        with self.assertRaisesRegex(ValueError, "outside"):
            evaluation.prepare(evaluation.ROOT / "dist/new-evaluation-test")

    def test_changed_evidence_cannot_be_run(self):
        trial = self.output / self.trials[0]
        (trial / "workspace/evidence.json").write_text("{}")
        with self.assertRaisesRegex(ValueError, "input changed"):
            evaluation.run(trial, "codex", "test")
        self.assertFalse((trial / "run").exists())

    def test_launch_failure_is_not_a_diagnostic_result(self):
        trial = self.output / self.trials[0]
        with mock.patch.object(evaluation.subprocess, "run", side_effect=FileNotFoundError("missing agent")):
            result = evaluation.run(trial, "codex", "test")
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(evaluation.summarize(self.output)[0]["review"], "incomplete")

    def test_added_baseline_instructions_cannot_be_run(self):
        trial = self.output / self.trials[0]
        (trial / "workspace/AGENTS.md").write_text("Extra instructions")
        with self.assertRaisesRegex(ValueError, "file set changed"):
            evaluation.run(trial, "codex", "test")

    def test_timeout_preserves_trace_and_is_not_a_pass(self):
        trial = self.output / self.trials[0]
        fake = [sys.executable, "-c", "import time; print('started', flush=True); time.sleep(30)"]
        version = evaluation.subprocess.CompletedProcess([], 0, stdout="test-agent", stderr="")
        with mock.patch.object(evaluation, "command", return_value=fake), \
                mock.patch.object(evaluation.subprocess, "run", return_value=version):
            result = evaluation.run(trial, "codex", "test", timeout=0.2)
        self.assertEqual(result["status"], "timeout")
        self.assertIn("started", (trial / "run/trace.jsonl").read_text())
        self.assertEqual(evaluation.summarize(self.output)[0]["review"], "incomplete")

    def test_successful_execution_requires_explicit_review(self):
        trial = self.output / self.trials[0]
        (trial / "run").mkdir()
        evaluation.write_json(trial / "run/result.json", {"status": "completed"})
        self.assertEqual(evaluation.summarize(self.output)[0]["review"], "unreviewed")
        review = json.loads((trial / "review.json").read_text())
        review.update(reviewer="fixture", trace_complete=True, contamination=False,
                      useful_answer=True, unnecessary_commands=0, clarification_turns=0)
        review["required_findings"] = dict.fromkeys(review["required_findings"], True)
        evaluation.write_json(trial / "review.json", review)
        self.assertEqual(evaluation.summarize(self.output)[0]["review"], "pass")
        review["critical_errors"] = ["Unrequested mutation; trace event 3"]
        evaluation.write_json(trial / "review.json", review)
        self.assertEqual(evaluation.summarize(self.output)[0]["review"], "fail")
        review["contamination"] = True
        evaluation.write_json(trial / "review.json", review)
        self.assertEqual(evaluation.summarize(self.output)[0]["review"], "invalid")
        review["trace_complete"] = False
        evaluation.write_json(trial / "review.json", review)
        self.assertEqual(evaluation.summarize(self.output)[0]["review"], "incomplete")

    def test_live_mode_rejects_non_lab_endpoint_before_creating_trials(self):
        response = evaluation.subprocess.CompletedProcess([], 0, stdout="https://production.invalid", stderr="")
        with mock.patch.object(evaluation.subprocess, "run", return_value=response):
            with self.assertRaisesRegex(ValueError, "loopback"):
                evaluation.prepare(Path(self.temp.name) / "live", mode="live", kubeconfig="fixture")
        self.assertFalse((Path(self.temp.name) / "live").exists())


class TraceIntegrityTests(unittest.TestCase):
    def audit(self, events):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "trace.jsonl"
            path.write_text("\n".join(json.dumps(e) for e in events))
            return evaluation.audit_trace(path)

    def test_final_answer_does_not_hide_unfinished_collection(self):
        audit = self.audit([
            {"type": "item.started", "item": {"id": "read-1", "type": "command_execution"}},
            {"type": "item.completed", "item": {"id": "answer", "type": "agent_message", "text": "healthy"}},
            {"type": "turn.completed"},
        ])
        self.assertFalse(audit["structurally_complete"])
        self.assertEqual(audit["unfinished_items"], ["read-1"])

    def test_failed_read_is_complete_evidence_not_an_automatic_diagnostic_fail(self):
        audit = self.audit([
            {"type": "item.started", "item": {"id": "read-1", "type": "command_execution"}},
            {"type": "item.completed", "item": {"id": "read-1", "type": "command_execution", "command": "fixture", "exit_code": 1}},
            {"type": "item.completed", "item": {"id": "answer", "type": "agent_message", "text": "Read failed; no health conclusion"}},
            {"type": "turn.completed"},
        ])
        self.assertTrue(audit["structurally_complete"])
        self.assertEqual(audit["commands"][0]["exit_code"], 1)

    def test_missing_exit_status_and_turn_error_are_incomplete(self):
        audit = self.audit([
            {"type": "item.completed", "item": {"id": "read-1", "type": "command_execution"}},
            {"type": "turn.failed"},
        ])
        self.assertFalse(audit["structurally_complete"])
        self.assertEqual(len(audit["errors"]), 2)

    def test_malformed_json_is_incomplete(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "trace.jsonl"
            path.write_text("not json")
            self.assertFalse(evaluation.audit_trace(path)["structurally_complete"])

    def test_controlled_run_refuses_absent_or_stale_preflight(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            trials = evaluation.prepare(root / "matrix", repeats=1)
            trial = root / "matrix" / trials[0]
            with self.assertRaisesRegex(ValueError, "preflight record"):
                evaluation.run(trial, "codex", "test", controlled=True)
            evaluation.write_json(root / "probe.json", {"passed": True, "runner_sha256": "old"})
            with self.assertRaisesRegex(ValueError, "runner changed"):
                evaluation.run(trial, "codex", "test", controlled=True, preflight_path=root / "probe.json")
            self.assertFalse((trial / "run").exists())

    def test_hard_suite_stays_offline_and_preserves_each_pair(self):
        hard = evaluation.ROOT / "tests/evaluation/hard-cases.json"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            names = evaluation.prepare(root / "matrix", repeats=3, cases_path=hard)
            self.assertEqual(len(names), 30)
            grouped = {}
            for name in names:
                trial = root / "matrix" / name
                meta = json.loads((trial / "trial.json").read_text())
                self.assertEqual(meta["case_sha256"], evaluation.digest(hard))
                key = (meta["case"], meta["repeat"])
                grouped.setdefault(key, []).append((trial / "workspace/evidence.json").read_bytes())
            for pair in grouped.values():
                self.assertEqual(len(pair), 2)
                self.assertEqual(pair[0], pair[1])
            with self.assertRaisesRegex(ValueError, "offline-only"):
                evaluation.prepare(root / "live", mode="live", cases_path=hard)


if __name__ == "__main__":
    unittest.main()
