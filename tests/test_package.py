"""Offline packaging tests: no Kubernetes, cloud calls, or credentials."""

import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("package_skill", ROOT / "scripts/package_skill.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class PackageTests(unittest.TestCase):
    def test_distribution_is_complete_and_contains_only_release_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            destination = module.package_distribution(Path(temporary) / "release")
            legal_files = {name for name in ("LICENSE", "NOTICE") if (ROOT / name).is_file()}
            self.assertEqual({p.name for p in destination.iterdir()},
                             {"skills", "README.md", "SOURCE.json"} | legal_files)
            self.assertEqual({p.name for p in (destination / "skills").iterdir()}, set(module.SKILLS))
            source = json.loads((destination / "SOURCE.json").read_text())
            self.assertEqual(source["commit"], module.git(ROOT, "rev-parse", "HEAD"))
            self.assertIsInstance(source["dirty"], bool)
            self.assertEqual(source["skills"], sorted(module.SKILLS))
            self.assertEqual(len(list(destination.rglob("SKILL.md"))), len(module.SKILLS))
            module.check_links(destination)
            with self.assertRaisesRegex(ValueError, "already exists"):
                module.package_distribution(destination)

    def test_failed_distribution_does_not_leave_partial_release(self):
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "release"
            original = module.package

            def fail_after_one(*args, **kwargs):
                if kwargs["skill"] == "service-connectivity-triage":
                    raise ValueError("Missing upstream reference")
                return original(*args, **kwargs)

            with mock.patch.object(module, "package", side_effect=fail_after_one):
                with self.assertRaisesRegex(ValueError, "Missing upstream"):
                    module.package_distribution(destination)
            self.assertFalse(destination.exists())
            self.assertEqual(list(Path(temporary).iterdir()), [])

    def test_all_skills_preserve_selected_sources_and_resolve_links(self):
        with tempfile.TemporaryDirectory() as temporary:
            for skill, selections in module.SKILLS.items():
                with self.subTest(skill=skill):
                    bundle = module.package(Path(temporary) / skill, skill=skill)
                    self.assertEqual([p.relative_to(bundle) for p in bundle.rglob("SKILL.md")],
                                     [Path("SKILL.md")])
                    module.check_links(bundle)
                    for label, path, selected in selections:
                        upstream = ROOT / path
                        vendor = bundle / "references" / label
                        metadata = json.loads((vendor / "UPSTREAM.json").read_text())
                        self.assertEqual(metadata["revision"], module.git(upstream, "rev-parse", "HEAD"))
                        self.assertEqual(metadata["path"], selected)
                        self.assertEqual((vendor / "LICENSE").read_bytes(), (upstream / "LICENSE").read_bytes())
                        for source in (upstream / selected).rglob("*"):
                            if source.is_file():
                                relative = source.relative_to(upstream / selected)
                                if "included_files" in metadata and str(relative) not in metadata["included_files"]:
                                    continue
                                target = vendor / ("guide.md" if str(relative) == "SKILL.md" else relative)
                                self.assertEqual(target.read_bytes(), source.read_bytes())

    def test_mysql_bundle_contains_only_pinned_diagnostic_references(self):
        with tempfile.TemporaryDirectory() as temporary:
            bundle = module.package(Path(temporary) / "cloud-sql-triage", skill="cloud-sql-triage")
            vendor = bundle / "references/planetscale-mysql"
            expected = {"references/" + name + ".md" for name in (
                "connection-management", "deadlocks", "row-locking-gotchas",
                "explain-analysis", "replication-lag")}
            self.assertEqual({str(p.relative_to(vendor)) for p in vendor.rglob("*") if p.is_file()},
                             expected | {"LICENSE", "UPSTREAM.json"})
            metadata = json.loads((vendor / "UPSTREAM.json").read_text())
            self.assertEqual(set(metadata["included_files"]), expected)
            self.assertEqual(metadata["entrypoint_mapping"], {})
            for relative in expected:
                self.assertEqual((vendor / relative).read_bytes(),
                                 (ROOT / "upstream/planetscale-database-skills/skills/mysql" / relative).read_bytes())

    def test_rejects_wrong_directory_name_and_unknown_skill(self):
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(ValueError, "leaf directory"):
                module.package(Path(temporary) / "wrong-name", skill="delivery-triage")
            with self.assertRaisesRegex(ValueError, "Unknown skill"):
                module.package(Path(temporary) / "unknown", skill="unknown")

    def test_broken_reference_and_symlink_fail_before_publish(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "repo"
            source = root / "skills/delivery-triage"
            source.mkdir(parents=True)
            (source / "SKILL.md").write_text("[required](references/missing.md)\n")
            destination = Path(temporary) / "out/delivery-triage"
            with self.assertRaisesRegex(ValueError, "Unresolved"):
                module.package(destination, root=root, skill="delivery-triage")
            self.assertFalse(destination.exists())
            (source / "SKILL.md").write_text("A skill\n")
            (source / "escape").symlink_to(Path(temporary))
            with self.assertRaisesRegex(ValueError, "symlinks"):
                module.package(destination, root=root, skill="delivery-triage")
            self.assertFalse(destination.exists())

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
            self.assertTrue((destination / "scripts/pod_config_compare.py").is_file())
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
