"""Offline packaging tests: no Kubernetes, cloud calls, or credentials."""

import json
from pathlib import Path
import shutil
import subprocess
import sys
import stat
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import package_skill as module


class PackageTests(unittest.TestCase):
    def test_builds_from_upstream_without_changing_source(self):
        def files(directory):
            return {str(p.relative_to(directory)): (p.read_bytes(), stat.S_IMODE(p.stat().st_mode))
                    for p in directory.rglob("*") if p.is_file()
                    and "__pycache__" not in p.parts and p.suffix != ".pyc"}

        before = files(ROOT / "skills")
        with tempfile.TemporaryDirectory() as temporary:
            for skill, selections in module.SKILLS.items():
                with self.subTest(skill=skill):
                    for label, _, _ in selections:
                        self.assertFalse((ROOT / "skills" / skill / "references" / label).exists())
                    first = module.package(Path(temporary) / "first" / skill, skill=skill)
                    second = module.package(Path(temporary) / "second" / skill, skill=skill)
                    self.assertEqual(files(first), files(second))
        self.assertEqual(files(ROOT / "skills"), before)

    def test_rejects_a_generated_copy_in_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "repo"
            shutil.copytree(ROOT / "skills", root / "skills")
            (root / "upstream").symlink_to(ROOT / "upstream", target_is_directory=True)
            original_git = module.git

            def git_at_real_root(directory, *args):
                return original_git(ROOT if directory == root else directory, *args)

            reference = root / "skills/workload-triage/references/google-gke-workload"
            reference.mkdir()
            (reference / "guide.md").write_text("stale copy")
            with mock.patch.object(module, "git", side_effect=git_at_real_root):
                with self.assertRaisesRegex(ValueError, "Generated reference"):
                    module.package(Path(temporary) / "workload-triage", root=root)
            self.assertEqual((reference / "guide.md").read_text(), "stale copy")

    def test_updating_only_the_gitlink_updates_the_bundled_reference(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "source"
            root.mkdir()
            module.git(root, "init", "-q")
            source = root / "skills/workload-triage"
            source.mkdir(parents=True)
            (source / "SKILL.md").write_text("See [guide](references/google-gke-workload/guide.md).\n")
            upstream = root / module.SUBMODULE
            selected = upstream / module.SELECTED
            selected.mkdir(parents=True)
            module.git(upstream, "init", "-q")
            (upstream / "LICENSE").write_text("Upstream fixture license\n")
            module.git(root, "config", "-f", ".gitmodules",
                       f"submodule.{module.SUBMODULE}.url", "https://example.invalid/upstream.git")
            for version in ("original", "updated"):
                (selected / "SKILL.md").write_text(version + "\n")
                module.git(upstream, "add", ".")
                module.git(upstream, "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                           "-c", "commit.gpgsign=false", "commit", "-qm", version)
                revision = module.git(upstream, "rev-parse", "HEAD")
                module.git(root, "update-index", "--add", "--cacheinfo",
                           f"160000,{revision},{module.SUBMODULE}")
                bundle = module.package(Path(temporary) / version / "workload-triage", root=root)
                reference = bundle / "references/google-gke-workload"
                self.assertEqual((reference / "guide.md").read_text(), version + "\n")
                self.assertEqual(json.loads((reference / "UPSTREAM.json").read_text())["revision"], revision)
                self.assertFalse((source / "references").exists())

    def test_distribution_is_complete_and_contains_only_bundle_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            destination = module.package_distribution(Path(temporary) / "bundle")
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
            self.assertEqual((destination / "LICENSE").read_bytes(), (ROOT / "LICENSE").read_bytes())
            with self.assertRaisesRegex(ValueError, "already exists"):
                module.package_distribution(destination)

    def test_distribution_refuses_an_unregistered_source_skill(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "repo"
            shutil.copytree(ROOT / "skills", root / "skills")
            shutil.copy2(ROOT / "LICENSE", root / "LICENSE")
            (root / "upstream").symlink_to(ROOT / "upstream", target_is_directory=True)
            new_skill = root / "skills/new-triage"
            new_skill.mkdir()
            (new_skill / "SKILL.md").write_text(
                "---\nname: new-triage\ndescription: Inspect a new service.\n---\n")
            original_git = module.git

            def git_at_real_root(directory, *args):
                return original_git(ROOT if directory == root else directory, *args)

            destination = Path(temporary) / "bundle"
            with mock.patch.object(module, "git", side_effect=git_at_real_root):
                with self.assertRaisesRegex(ValueError, "unregistered.*new-triage"):
                    module.package_distribution(destination, root=root)
            self.assertFalse(destination.exists())

    def test_failed_distribution_does_not_leave_partial_bundle(self):
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "bundle"
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
                    for source in (ROOT / "skills" / skill).rglob("*"):
                        if source.is_file() and "__pycache__" not in source.parts and source.suffix != ".pyc":
                            target = bundle / source.relative_to(ROOT / "skills" / skill)
                            self.assertEqual(target.read_bytes(), source.read_bytes())
                            self.assertEqual(stat.S_IMODE(target.stat().st_mode),
                                             stat.S_IMODE(source.stat().st_mode))
                    self.assertFalse(any(p.is_symlink() or p.name in ("__pycache__", "profile.yaml")
                                         or p.suffix == ".pyc" for p in bundle.rglob("*")))
                    with self.assertRaisesRegex(ValueError, "already exists"):
                        module.package(bundle, skill=skill)
                    for name, consumers in module.SHARED_REFERENCES.items():
                        if skill in consumers:
                            self.assertEqual((bundle / "references" / name).read_bytes(),
                                             (ROOT / "shared" / name).read_bytes())
                    license_text = (ROOT / "LICENSE").read_bytes()
                    self.assertEqual((ROOT / "skills" / skill / "LICENSE").read_bytes(), license_text)
                    self.assertEqual((bundle / "LICENSE").read_bytes(), license_text)
                    for label, path, selected in selections:
                        upstream = ROOT / path
                        vendor = bundle / "references" / label
                        metadata = json.loads((vendor / "UPSTREAM.json").read_text())
                        self.assertEqual(metadata["revision"], module.git(upstream, "rev-parse", "HEAD"))
                        self.assertEqual(metadata["path"], selected)
                        self.assertFalse(metadata["modified"])
                        self.assertEqual(metadata["entrypoint_mapping"],
                                         {} if label in module.REFERENCE_FILES else {"SKILL.md": "guide.md"})
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
            shutil.copytree(ROOT / "shared", root / "shared")
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
