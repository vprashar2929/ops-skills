"""Offline packaging tests: no Kubernetes, cloud calls, or credentials."""

import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("package_skill", ROOT / "scripts/package_skill.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class PackageTests(unittest.TestCase):
    def test_self_contained_and_preserves_upstream(self):
        with tempfile.TemporaryDirectory() as temporary:
            destination = module.package(Path(temporary) / "workload-triage")
            vendor = destination / "references/google-gke-workload"
            upstream = ROOT / module.SUBMODULE
            self.assertEqual((vendor / "guide.md").read_bytes(), (upstream / module.SELECTED / "SKILL.md").read_bytes())
            self.assertEqual((vendor / "LICENSE").read_bytes(), (upstream / "LICENSE").read_bytes())
            metadata = json.loads((vendor / "UPSTREAM.json").read_text())
            self.assertEqual(metadata["revision"], module.git(upstream, "rev-parse", "HEAD"))
            self.assertFalse(metadata["modified"])
            self.assertEqual(metadata["entrypoint_mapping"], {"SKILL.md": "guide.md"})
            self.assertEqual(
                [p.relative_to(destination) for p in destination.rglob("*") if p.name.lower() == "skill.md"],
                [Path("SKILL.md")],
            )
            self.assertTrue((destination / "SKILL.md").is_file())
            self.assertTrue((destination / "scripts/config_summary.py").is_file())
            self.assertFalse(any(p.name == "__pycache__" or p.suffix == ".pyc"
                                 for p in destination.rglob("*")))
            self.assertFalse(any(p.is_symlink() for p in destination.rglob("*")))
            self.assertFalse(any(p.name == "profile.yaml" for p in destination.rglob("*")))
            with self.assertRaisesRegex(ValueError, "already exists"):
                module.package(destination)

    def test_rejects_changed_or_unrecorded_upstream(self):
        # A synthetic repo exercises refusal without changing the real dependency.
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "repo"
            root.mkdir()
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            upstream = root / module.SUBMODULE
            upstream.mkdir(parents=True)
            subprocess.run(["git", "init", "-q", str(upstream)], check=True)
            (upstream / "file").write_text("original\n")
            subprocess.run(["git", "-C", str(upstream), "add", "file"], check=True)
            subprocess.run(["git", "-C", str(upstream), "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "-c", "commit.gpgsign=false", "commit", "-qm", "fixture"], check=True)
            revision = module.git(upstream, "rev-parse", "HEAD")
            subprocess.run(["git", "-C", str(root), "update-index", "--add", "--cacheinfo", f"160000,{revision},{module.SUBMODULE}"], check=True)
            (upstream / "file").write_text("edited\n")
            with self.assertRaisesRegex(ValueError, "local changes"):
                module.package(Path(temporary) / "out", root=root)
            subprocess.run(["git", "-C", str(upstream), "add", "file"], check=True)
            subprocess.run(["git", "-C", str(upstream), "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "-c", "commit.gpgsign=false", "commit", "-qm", "new revision"], check=True)
            with self.assertRaisesRegex(ValueError, "differs from recorded"):
                module.package(Path(temporary) / "out", root=root)


if __name__ == "__main__":
    unittest.main()
