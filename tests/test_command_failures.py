"""Execute the documented pipeline with a fake kubectl; never contact a cluster."""

from pathlib import Path
import re
import shutil
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
GUIDANCE = ROOT / "skills/workload-triage/references/targeting.md"


@unittest.skipUnless(shutil.which("bash") and shutil.which("jq"), "requires bash and jq")
class CommandFailureTests(unittest.TestCase):
    def run_example(self, collector):
        section = GUIDANCE.read_text().split("## Preserve command failures", 1)[1]
        example = re.search(r"```bash\n(.*?)\n```", section, re.DOTALL).group(1)
        # A shell function shadows kubectl, so this test cannot invoke the real CLI.
        script = 'context=fixture namespace=fixture workload=deployment/example\n'
        script += 'kubectl() {\n' + collector + '\n}\n' + example
        return subprocess.run(["bash", "-c", script], capture_output=True, text=True, timeout=5)

    def test_failed_collection_keeps_nonzero_status_and_stderr(self):
        for message in ("authentication failed", "request timed out", "namespace not found"):
            with self.subTest(message=message):
                result = self.run_example(f'printf "%s\\n" "{message}" >&2; return 23')
                self.assertEqual(result.returncode, 23)
                self.assertEqual(result.stdout, "")
                self.assertIn(message, result.stderr)

    def test_successful_collection_is_projected(self):
        result = self.run_example('printf \'%s\\n\' \'{"metadata":{"name":"example"},"status":{"readyReplicas":2}}\'')
        self.assertEqual(result.returncode, 0)
        self.assertIn('"readyReplicas": 2', result.stdout)
        self.assertEqual(result.stderr, "")

    def test_invalid_json_remains_a_failure(self):
        result = self.run_example('printf "%s\\n" "invalid JSON"')
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue(result.stderr)


if __name__ == "__main__":
    unittest.main()
