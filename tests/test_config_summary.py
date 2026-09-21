"""Offline behavior checks for compact config projections; no cloud access."""

import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "skills/workload-triage/scripts/config_summary.py"
spec = importlib.util.spec_from_file_location("config_summary", HELPER)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
SENTINEL = "DO_NOT_EMIT_sensitive_fixture_value"


def fixture():
    secret = {"apiVersion": "v1", "kind": "Secret", "metadata": {
        "name": "app-config", "namespace": "demo", "annotations": {"last-applied": SENTINEL},
        "ownerReferences": [{"kind": "ExternalSecret", "name": "supplier", "uid": "owner-1"}]},
        "data": {"COMMON": SENTINEL, "TOKEN": SENTINEL}, "stringData": {"TOKEN": SENTINEL}}
    external = {"apiVersion": "external-secrets.io/v1", "kind": "ExternalSecret",
        "metadata": {"name": "supplier", "namespace": "demo"},
        "spec": {"secretStoreRef": {"kind": "ClusterSecretStore", "name": "default"},
                 "target": {"name": "app-config", "creationPolicy": "Owner"},
                 "data": [{"secretKey": "COMMON", "remoteRef": {"key": "common"}},
                          {"secretKey": "TOKEN", "remoteRef": {"key": "token", "version": "7"},
                           "sourceRef": {"storeRef": {"kind": "ClusterSecretStore", "name": "shared"}}}]},
        "status": {"refreshTime": "2026-09-21T09:00:00Z", "conditions": [
            {"type": "Ready", "status": "False", "reason": "SecretSyncedError", "message": SENTINEL}]}}
    return {"apiVersion": "v1", "kind": "List", "items": [secret, external]}


class ConfigSummaryTests(unittest.TestCase):
    def run_helper(self, document, *args):
        return subprocess.run([sys.executable, str(HELPER), *args], input=json.dumps(document),
                              capture_output=True, text=True, timeout=5)

    def test_named_key_override_and_no_values(self):
        result = self.run_helper(fixture(), "--key", "TOKEN")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn(SENTINEL, result.stdout + result.stderr)
        summary = json.loads(result.stdout)["objects"]
        mapping = summary[1]["requestedKey"]["explicitMappings"][0]
        self.assertEqual(mapping["store"]["name"], "shared")
        self.assertEqual(mapping["remoteRef"], {"key": "token", "version": "7"})
        self.assertEqual(summary[1]["targetKeyComparison"]["missing"]["count"], 0)
        self.assertEqual(summary[0]["owners"][0]["uid"], "owner-1")
        self.assertEqual(summary[1]["conditions"][0]["status"], "False")

    def test_full_comparison_precedes_sampling(self):
        document = fixture()
        document["items"][0]["data"] = {"unexpected": SENTINEL}
        document["items"][0].pop("stringData")
        document["items"][1]["spec"]["data"] = [
            {"secretKey": f"KEY_{i:03d}", "remoteRef": {"key": str(i)}} for i in range(87)]
        comparison = module.summarize(document)["objects"][1]["targetKeyComparison"]
        self.assertEqual(comparison["missing"]["count"], 87)
        self.assertEqual(len(comparison["missing"]["names"]), 20)
        self.assertEqual(comparison["missing"]["omitted"], 67)
        self.assertEqual(comparison["extra"]["names"], ["unexpected"])

    def test_namespace_mismatch_does_not_compare(self):
        document = fixture()
        document["items"][0]["metadata"]["namespace"] = "other-client"
        self.assertEqual(module.summarize(document)["objects"][1]["targetKeyComparison"]["status"],
                         "not-collected")

    def test_template_and_datafrom_skip_comparison_without_values(self):
        for patch in ({"dataFrom": [{"extract": {"key": "source"}}]},
                      {"target": {"name": "app-config", "template": {"data": {"generated": SENTINEL}}}}):
            document = fixture()
            document["items"][1]["spec"].update(copy.deepcopy(patch))
            result = self.run_helper(document)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn(SENTINEL, result.stdout + result.stderr)
            self.assertEqual(json.loads(result.stdout)["objects"][1]["targetKeyComparison"]["status"],
                             "indeterminate")

    def test_unspecified_version_and_absent_key_not_invented(self):
        summary = module.summarize(fixture(), "COMMON")["objects"][1]
        self.assertIsNone(summary["requestedKey"]["explicitMappings"][0]["remoteRef"]["version"])
        summary = module.summarize(fixture(), "missing")["objects"]
        self.assertFalse(summary[0]["requestedKey"]["present"])
        self.assertEqual(summary[1]["requestedKey"]["explicitMappings"], [])

    def test_configmap_binary_keys_without_values(self):
        document = {"apiVersion": "v1", "kind": "ConfigMap", "metadata": {"name": "options"},
                    "data": {"text": SENTINEL}, "binaryData": {"binary": SENTINEL}}
        result = self.run_helper(document)
        self.assertEqual(json.loads(result.stdout)["objects"][0]["keys"]["names"], ["binary", "text"])
        self.assertNotIn(SENTINEL, result.stdout + result.stderr)

    def test_secret_manifest_stringdata_keys_without_values(self):
        document = fixture()
        secret = document["items"][0]
        secret.pop("data")
        secret["stringData"] = {"COMMON": SENTINEL, "TOKEN": SENTINEL}
        result = self.run_helper(document, "--key", "COMMON")
        summary = json.loads(result.stdout)["objects"]
        self.assertTrue(summary[0]["requestedKey"]["present"])
        self.assertEqual(summary[1]["targetKeyComparison"]["missing"]["count"], 0)
        self.assertNotIn(SENTINEL, result.stdout + result.stderr)

    def test_malformed_key_maps_rejected_without_emitting_list_contents(self):
        for field, kind in (("data", "Secret"), ("stringData", "Secret"), ("binaryData", "ConfigMap")):
            document = {"apiVersion": "v1", "kind": kind, "metadata": {"name": "bad"},
                        field: [SENTINEL]}
            result = self.run_helper(document)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(result.stdout, "")
            self.assertNotIn(SENTINEL, result.stderr)

    def test_large_store_override_set_is_sampled(self):
        document = fixture()["items"][1]
        document["spec"]["data"] = [{"secretKey": f"KEY_{i}", "remoteRef": {"key": str(i)},
                                      "sourceRef": {"storeRef": {"name": f"store-{i}"}}}
                                     for i in range(2000)]
        result = self.run_helper(document, "--key", "KEY_1999")
        summary = json.loads(result.stdout)["objects"][0]
        self.assertEqual(summary["explicitKeyStores"]["count"], 2000)
        self.assertEqual(summary["explicitKeyStores"]["omitted"], 1980)
        self.assertEqual(len(summary["explicitKeyStores"]["entries"]), 20)
        self.assertEqual(summary["requestedKey"]["explicitMappings"][0]["store"]["name"], "store-1999")
        self.assertLess(len(result.stdout), 5000)

    def test_invalid_empty_or_unsupported_input_fails_without_echo(self):
        for raw in ("", SENTINEL, "{}", "[]", json.dumps({"kind": "Pod", "message": SENTINEL}),
                    json.dumps({"kind": "List", "items": [fixture()["items"][0]] * 21})):
            with self.subTest(raw=raw[:20]):
                result = subprocess.run([sys.executable, str(HELPER)], input=raw,
                                        capture_output=True, text=True, timeout=5)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, "")
                self.assertNotIn(SENTINEL, result.stderr)


if __name__ == "__main__":
    unittest.main()
