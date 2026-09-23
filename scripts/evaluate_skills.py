#!/usr/bin/env python3
"""Prepare paired trials and capture fresh agent runs; never auto-grade diagnosis."""

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import random
import re
import shutil
import signal
import socket
import subprocess
import sys
import time

from package_skill import ROOT, package


CASES = ROOT / "tests/evaluation/cases.json"


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare(destination, repeats=3, mode="offline", kubeconfig=None, seed=17, cases_path=CASES):
    destination = Path(destination).resolve()
    if destination.exists():
        raise ValueError("Choose a new output directory; previous trials are never overwritten")
    if destination.is_relative_to(ROOT):
        raise ValueError("Keep evaluation workspaces/results outside the source repository")
    if repeats < 1:
        raise ValueError("repeats must be positive")
    cases_path = Path(cases_path)
    cases = json.loads(cases_path.read_text())
    if mode == "live" and cases_path.resolve() != CASES.resolve():
        raise ValueError("Custom evidence suites are offline-only")
    if mode == "live":
        if kubeconfig is None:
            raise ValueError("Live trials require the disposable lab kubeconfig")
        kubeconfig = Path(kubeconfig).resolve()
        # Local metadata only. Never contact whichever cluster happens to be active.
        check = subprocess.run([
            "kubectl", "--kubeconfig", str(kubeconfig), "--context", "kind-ops-skills",
            "config", "view", "--minify", "-o", "jsonpath={.clusters[0].cluster.server}"
        ], capture_output=True, text=True, check=True, timeout=20)
        if check.stdout.strip() != "https://127.0.0.1:16443":
            raise ValueError("Live evaluation accepts only the documented loopback kind lab")
    destination.mkdir(parents=True, mode=0o700)
    revision = subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip()
    dirty = bool(subprocess.check_output(["git", "-C", str(ROOT), "status", "--porcelain"], text=True).strip())
    order = [(case, arm, repeat) for repeat in range(1, repeats + 1)
             for case in cases for arm in ("baseline", "skill")]
    random.Random(seed).shuffle(order)
    trials = []
    for index, (case, arm, repeat) in enumerate(order, 1):
        trial = destination / f"{index:03d}-{case['id']}-{arm}-{repeat}"
        workspace = trial / "workspace"
        workspace.mkdir(parents=True)
        profile = (ROOT / "examples/kind/profile.yaml").read_text()
        if case["id"] == "identity-mismatch":
            profile = profile.replace(":16443", ":16444")
        (workspace / "profile.yaml").write_text(profile)
        prompt = "Profile: ./profile.yaml\nEnvironment: local\nCluster: apps\n"
        prompt += case["request"] + "\nRead-only. Keep secret values out of output.\n"
        if mode == "offline":
            write_json(workspace / "evidence.json", {
                "provenance": "Synthetic, manually authored evidence; not a live collection",
                "observation_time": "2026-09-23T12:00:00Z",
                "command_session_ids": "unavailable", "evidence": case["evidence"]})
            prompt += ("Analyze only the supplied evidence.json as historical offline evidence. "
                       "Do not contact infrastructure or fetch additional evidence. State missing coverage.\n")
        else:
            shutil.copy2(kubeconfig, workspace / "kubeconfig")
            (workspace / "kubeconfig").chmod(0o600)
            prompt += "Use only ./kubeconfig for the disposable local cluster. No cloud calls.\n"
        prompt += ("Read only files in this workspace and the tools needed for the task. "
                   "Do not inspect evaluator files, setup manifests, other trials, or the source repository.\n")
        if arm == "skill":
            package(workspace / "skill" / case["skill"], skill=case["skill"])
            prompt += f"Read and follow ./skill/{case['skill']}/SKILL.md and relevant linked resources.\n"
        else:
            prompt += "Do not use installed operational triage skills for this trial.\n"
        (trial / "prompt.txt").write_text(prompt)
        manifest = {
            "case": case["id"], "arm": arm, "repeat": repeat, "mode": mode,
            "source_revision": revision, "source_dirty": dirty, "seed": seed,
            "case_sha256": digest(cases_path), "prompt_sha256": digest(trial / "prompt.txt"),
            "workspace_sha256": {str(p.relative_to(workspace)): digest(p)
                                 for p in sorted(workspace.rglob("*")) if p.is_file()},
        }
        write_json(trial / "trial.json", manifest)
        # Evaluator-only file; deliberately outside the agent workspace.
        write_json(trial / "review.json", {
            "reviewer": None, "trace_complete": None, "contamination": None,
            "required_findings": {finding: None for finding in case["required_findings"]},
            "unsupported_claims": [], "critical_errors": [],
            "unnecessary_commands": None, "clarification_turns": None,
            "useful_answer": None, "notes": "Unreviewed; record evidence/trace references for each judgment"
        })
        trials.append(trial.name)
    write_json(destination / "matrix.json", {"trials": trials, "mode": mode, "repeats": repeats, "seed": seed})
    return trials


def controlled_config(workspace):
    """CLI-local restrictions; never edit user configuration or copy credentials."""
    workspace = Path(workspace).resolve()
    skill_roots = [Path.home() / ".codex/skills", Path.home() / ".agents/skills"]
    disabled = [p.parent for root in skill_roots if root.exists() for p in root.rglob("SKILL.md")]
    settings = [
        'project_doc_max_bytes=0', 'developer_instructions=""',
        'features.skip_host_skill_discovery=true', 'features.plugins=false',
        'features.apps=false', 'features.hooks=false', 'features.multi_agent=false',
        'features.browser_use=false', 'features.computer_use=false',
        'features.memories=false', 'features.shell_snapshot=false',
        'web_search="disabled"', 'allow_login_shell=false',
        'shell_environment_policy.inherit="core"',
        'shell_environment_policy.ignore_default_excludes=false',
        'model_reasoning_effort="medium"', 'approval_policy="never"',
        'default_permissions="evaluation"',
        'permissions.evaluation.filesystem={":minimal"="read", "/opt/homebrew"="read", "/usr/local/bin"="read", '
        + json.dumps(str(workspace.parent.parent)) + '="deny", '
        + json.dumps(str(ROOT)) + '="deny", '
        + json.dumps(str(Path.home())) + '="deny", '
        + json.dumps(str(workspace)) + '="read"}',
        'permissions.evaluation.network.enabled=false',
        'skills.config=[' + ','.join('{path=' + json.dumps(str(p)) + ',enabled=false}' for p in sorted(disabled)) + ']',
    ]
    return [part for setting in settings for part in ("-c", setting)]


def command(agent, model, workspace, controlled=False):
    if agent == "codex":
        return ["codex", "exec", "--ignore-user-config", "--ignore-rules", "--ephemeral",
                "--skip-git-repo-check", *(controlled_config(workspace) if controlled else ["--sandbox", "read-only"]), "--json", "--model", model,
                "-C", str(workspace), "-"]
    return ["claude", "--print", "--verbose", "--output-format", "stream-json",
            "--model", model, "--no-session-persistence", "--permission-mode", "default"]


def run(trial, agent, model, timeout=300, controlled=False, preflight_path=None):
    trial = Path(trial).resolve()
    if timeout <= 0:
        raise ValueError("timeout must be positive")
    manifest = json.loads((trial / "trial.json").read_text())
    if controlled and (agent != "codex" or manifest["mode"] != "offline"):
        raise ValueError("Controlled mode currently supports only offline Codex trials")
    if controlled:
        if preflight_path is None:
            raise ValueError("Controlled trials require a successful --preflight record")
        probe = json.loads(Path(preflight_path).read_text())
        if probe.get("passed") is not True or probe.get("runner_sha256") != digest(Path(__file__)):
            raise ValueError("Preflight failed or runner changed; rerun preflight")
    workspace = trial / "workspace"
    paths = list(workspace.rglob("*"))
    if any(p.is_symlink() for p in paths) or {str(p.relative_to(workspace)) for p in paths if p.is_file()} != set(manifest["workspace_sha256"]):
        raise ValueError("Trial file set changed; prepare a fresh matrix")
    for relative, expected in manifest["workspace_sha256"].items():
        if digest(workspace / relative) != expected:
            raise ValueError(f"Trial input changed: {relative}; prepare a fresh matrix")
    if digest(trial / "prompt.txt") != manifest["prompt_sha256"]:
        raise ValueError("Prompt changed; prepare a fresh matrix")
    output = trial / "run"
    output.mkdir(mode=0o700)  # Refuse an accidental rerun/overwrite.
    cmd = command(agent, model, workspace, controlled)
    env = dict(os.environ)
    if manifest["mode"] == "live":
        env["KUBECONFIG"] = str(workspace / "kubeconfig")
    started = datetime.now(timezone.utc).isoformat()
    start = time.monotonic()
    result = {"agent": agent, "model": model, "command": cmd, "started_at": started,
              "status": "launching", "exit_code": None,
              "agent_executable": shutil.which(agent),
              "controlled": controlled,
              "preflight": str(preflight_path) if preflight_path else None,
              "isolation": ("Explicit evaluator/source/home read denials, no writes/network, fixed CLI restrictions; built-in catalog remains. See preflight."
                            if controlled else "Fresh process/workspace; host account and global extensions are not isolated. Review trace for contamination.")}
    try:
        version = subprocess.run([agent, "--version"], capture_output=True, text=True, timeout=20, check=True)
        result["agent_version"] = version.stdout.strip()
        with (output / "trace.jsonl").open("w") as stdout, (output / "stderr.txt").open("w") as stderr:
            process = subprocess.Popen(cmd, cwd=workspace, env=env, stdin=subprocess.PIPE,
                                       stdout=stdout, stderr=stderr, text=True, start_new_session=True)
            try:
                process.communicate((trial / "prompt.txt").read_text(), timeout=timeout)
                result.update(status="completed" if process.returncode == 0 else "failed", exit_code=process.returncode)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.communicate(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.communicate()
                result.update(status="timeout", exit_code=process.returncode)
    except (OSError, subprocess.SubprocessError) as error:
        result.update(status="blocked", error=str(error))
    finally:
        result["elapsed_seconds"] = round(time.monotonic() - start, 3)
        if agent == "codex" and (output / "trace.jsonl").exists():
            result["trace_audit"] = audit_trace(output / "trace.jsonl")
        write_json(output / "result.json", result)
    return result


def audit_trace(path):
    """Structural checks only; missing claimed calls still require trace review."""
    started, completed, commands = set(), set(), []
    final, ended, errors = False, False, []
    try:
        for line in Path(path).read_text().splitlines():
            event = json.loads(line)
            item = event.get("item", {})
            if event.get("type") == "item.started":
                started.add(item.get("id"))
            if event.get("type") == "item.completed":
                completed.add(item.get("id"))
                if item.get("type") == "command_execution":
                    commands.append({"id": item.get("id"), "command": item.get("command"),
                                     "exit_code": item.get("exit_code")})
                    if item.get("exit_code") is None:
                        errors.append("Command result lacks exit status")
                if item.get("type") == "agent_message":
                    final = bool(item.get("text"))
            if event.get("type") == "turn.completed":
                ended = True
            if event.get("type") in ("error", "turn.failed"):
                errors.append(event.get("type"))
    except (ValueError, OSError) as error:
        errors.append(str(error))
    return {"structurally_complete": ended and final and not (started - completed) and not errors,
            "unfinished_items": sorted(str(x) for x in started - completed),
            "errors": errors, "commands": commands,
            "limitation": "Cannot verify claims about tool calls absent from the trace"}


def preflight(destination):
    """Probe actual filesystem/network enforcement without an AI or real credentials."""
    destination = Path(destination).resolve()
    destination.mkdir(mode=0o700)
    workspace = destination / "workspace"
    workspace.mkdir()
    (workspace / "allowed.txt").write_text("synthetic-inside")
    (destination / "outside.txt").write_text("synthetic-outside")
    config = controlled_config(workspace)
    # prompt-input lacks --ignore-user-config in CLI 0.156.1. Its output is only
    # a discovery diagnostic, not proof of the exact exec prompt.
    debug = subprocess.run(["codex", "debug", "prompt-input", *config,
                            "Evaluation preflight; no tools needed."], cwd=workspace,
                           capture_output=True, text=True, timeout=30)
    (destination / "prompt-input.json").write_text(debug.stdout)
    (destination / "prompt-input.stderr").write_text(debug.stderr)
    rendered = debug.stdout
    text_blocks = []
    if debug.returncode == 0:
        for message in json.loads(rendered):
            text_blocks.extend(c.get("text", "") for c in message.get("content", []))
    catalogs = [text for text in text_blocks if "<skills_instructions>" in text]
    skill_names = sorted(set(re.findall(r"^- ([a-z][\w-]*):", "\n".join(catalogs), re.MULTILINE)))
    builtin_names = {"imagegen", "openai-docs", "plugin-creator", "review-agent", "skill-creator", "skill-installer"}
    discovery = {"exit_code": debug.returncode,
                 "skill_catalog_present": "<skills_instructions>" in rendered or "### Available skills" in rendered,
                 "skill_names": skill_names,
                 "unexpected_skills": sorted(set(skill_names) - builtin_names),
                 "repo_instructions_present": "Skill maintenance requirements" in rendered,
                 "sha256": hashlib.sha256(rendered.encode()).hexdigest(),
                 "limitation": "debug command does not support ignore-user-config; not the exact exec prompt"}
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        port = listener.getsockname()[1]
        probe = (
            "import json,pathlib,socket; r={}\n"
            "r['inside_read']=pathlib.Path('allowed.txt').read_text()=='synthetic-inside'\n"
            "try: pathlib.Path('../outside.txt').read_text(); r['outside_denied']=False\n"
            "except PermissionError: r['outside_denied']=True\n"
            "try: pathlib.Path('write-test.txt').write_text('synthetic'); r['write_denied']=False\n"
            "except PermissionError: r['write_denied']=True\n"
            "s=socket.socket(); s.settimeout(2)\n"
            f"try: s.connect(('127.0.0.1',{port})); r['network_denied']=False\n"
            "except PermissionError: r['network_denied']=True\n"
            "except OSError as e: r['network_denied']=False; r['network_error']=str(e)\n"
            "print(json.dumps(r))\n"
        )
        check = subprocess.run(["codex", "sandbox", *config, "-C", str(workspace),
                                "--include-managed-config", "-P", "evaluation", "--",
                                sys.executable, "-c", probe], capture_output=True,
                               text=True, timeout=30)
    (destination / "sandbox.stdout").write_text(check.stdout)
    (destination / "sandbox.stderr").write_text(check.stderr)
    try:
        boundaries = json.loads(check.stdout)
    except ValueError:
        boundaries = {}
    passed = (check.returncode == 0 and all(boundaries.get(k) is True for k in (
        "inside_read", "outside_denied", "write_denied", "network_denied"))
        and discovery["exit_code"] == 0 and not discovery["unexpected_skills"]
        and not discovery["repo_instructions_present"])
    result = {"passed": passed, "runner_sha256": digest(Path(__file__)), "discovery": discovery, "boundaries": boundaries,
              "sandbox_exit_code": check.returncode, "config": config,
              "scope": "Local Codex CLI boundary probe; inference service still uses existing authentication"}
    write_json(destination / "preflight.json", result)
    return result


def summarize(directory):
    """Keep execution status separate from the reviewer verdict; never infer a pass."""
    directory = Path(directory)
    matrix = json.loads((directory / "matrix.json").read_text())
    rows = []
    for name in matrix["trials"]:
        trial = directory / name
        manifest = json.loads((trial / "trial.json").read_text())
        result_path = trial / "run/result.json"
        result = json.loads(result_path.read_text()) if result_path.exists() else {"status": "not-run"}
        review = json.loads((trial / "review.json").read_text())
        complete = (bool(review["reviewer"]) and review["trace_complete"] is True
                    and isinstance(review["contamination"], bool)
                    and isinstance(review["useful_answer"], bool)
                    and all(isinstance(v, bool) for v in review["required_findings"].values())
                    and type(review["unnecessary_commands"]) is int
                    and type(review["clarification_turns"]) is int)
        verdict = "unreviewed"
        if complete:
            verdict = "invalid" if review["contamination"] else "pass"
            if not review["contamination"] and (not review["useful_answer"]
                    or not all(review["required_findings"].values())
                    or review["unsupported_claims"] or review["critical_errors"]):
                verdict = "fail"
        if (result["status"] != "completed" or review["trace_complete"] is False
                or result.get("trace_audit", {}).get("structurally_complete") is False):
            verdict = "incomplete"
        rows.append({"trial": name, "case": manifest["case"], "arm": manifest["arm"],
                     "repeat": manifest["repeat"], "execution": result["status"],
                     "review": verdict, "elapsed_seconds": result.get("elapsed_seconds")})
    return rows


def run_matrix(directory, model, preflight_path, jobs=1, timeout=180):
    directory = Path(directory).resolve()
    matrix = json.loads((directory / "matrix.json").read_text())
    plan = directory / "execution.json"
    with plan.open("x") as stream:
        json.dump({"agent": "codex", "model": model, "jobs": jobs, "timeout": timeout,
                   "runner_sha256": digest(Path(__file__)), "preflight": str(preflight_path)}, stream)

    def execute(name):
        try:
            result = run(directory / name, "codex", model, timeout, True, preflight_path)
            row = {"trial": name, "status": result["status"],
                   "trace_complete": result.get("trace_audit", {}).get("structurally_complete")}
        except (ValueError, OSError) as error:
            row = {"trial": name, "status": "blocked", "error": str(error)}
        print(json.dumps(row), flush=True)
        return row

    with ThreadPoolExecutor(max_workers=jobs) as pool:
        results = list(pool.map(execute, matrix["trials"]))
    write_json(directory / "execution-results.json", results)
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest="action", required=True)
    prep = actions.add_parser("prepare")
    prep.add_argument("destination", type=Path)
    prep.add_argument("--repeats", type=int, default=3)
    prep.add_argument("--mode", choices=("offline", "live"), default="offline")
    prep.add_argument("--kubeconfig", type=Path)
    prep.add_argument("--seed", type=int, default=17)
    prep.add_argument("--cases", type=Path, default=CASES)
    execute = actions.add_parser("run")
    execute.add_argument("trial", type=Path)
    execute.add_argument("--agent", choices=("codex", "claude"), required=True)
    execute.add_argument("--model", required=True)
    execute.add_argument("--timeout", type=int, default=300)
    execute.add_argument("--controlled", action="store_true")
    execute.add_argument("--preflight", type=Path)
    report = actions.add_parser("summarize")
    report.add_argument("directory", type=Path)
    probe = actions.add_parser("preflight")
    probe.add_argument("destination", type=Path)
    batch = actions.add_parser("run-matrix")
    batch.add_argument("directory", type=Path)
    batch.add_argument("--model", required=True)
    batch.add_argument("--preflight", type=Path, required=True)
    batch.add_argument("--jobs", type=int, choices=(1, 2), default=1)
    batch.add_argument("--timeout", type=int, default=180)
    args = parser.parse_args()
    try:
        if args.action == "run-matrix":
            results = run_matrix(args.directory, args.model, args.preflight, args.jobs, args.timeout)
            return 0 if all(r["status"] == "completed" and r["trace_complete"] for r in results) else 1
        elif args.action == "preflight":
            result = preflight(args.destination)
            print(json.dumps(result))
            return 0 if result["passed"] else 1
        elif args.action == "prepare":
            print(json.dumps(prepare(args.destination, args.repeats, args.mode, args.kubeconfig, args.seed, args.cases)))
        elif args.action == "summarize":
            print(json.dumps(summarize(args.directory), indent=2))
        else:
            result = run(args.trial, args.agent, args.model, args.timeout, args.controlled, args.preflight)
            print(json.dumps(result))
            return 0 if result["status"] == "completed" else 1
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        parser.exit(1, f"Evaluation failed: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
