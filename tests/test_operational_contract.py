"""Verify shared guidance is maintained once and assembled into complete skills."""

from pathlib import Path
import shutil
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import package_skill as packager


class OperationalContractTests(unittest.TestCase):
    def test_shared_selections_match_skill_references(self):
        for name, consumers in packager.SHARED_REFERENCES.items():
            linked = {p.parent.name for p in (ROOT / "skills").glob("*/SKILL.md")
                      if f"(references/{name})" in p.read_text()}
            self.assertEqual(consumers, linked)
            self.assertEqual(list((ROOT / "skills").glob(f"*/references/{name}")), [])

    def test_one_shared_edit_updates_multiple_packages(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "source"
            shutil.copytree(ROOT / "shared", root / "shared")
            for skill in ("delivery-triage", "kafka-triage"):
                shutil.copytree(ROOT / "skills" / skill, root / "skills" / skill)
            for version in ("original", "updated"):
                content = f"# {version} shared guidance\n"
                (root / "shared/operations.md").write_text(content)
                for skill in ("delivery-triage", "kafka-triage"):
                    bundle = packager.package(Path(temporary) / version / skill, root=root, skill=skill)
                    self.assertEqual((bundle / "references/operations.md").read_text(), content)
                    packager.check_links(bundle)

    def test_missing_duplicate_or_symlinked_shared_source_is_rejected(self):
        for case in ("missing", "duplicate", "symlink"):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary) / "source"
                source = root / "skills/delivery-triage"
                shutil.copytree(ROOT / "skills/delivery-triage", source)
                shared = root / "shared/operations.md"
                shared.parent.mkdir()
                if case == "duplicate":
                    shared.write_text("canonical")
                    (source / "references").mkdir(exist_ok=True)
                    (source / "references/operations.md").write_text("stale copy")
                elif case == "symlink":
                    shared.symlink_to(ROOT / "shared/operations.md")
                destination = Path(temporary) / "delivery-triage"
                with self.assertRaises(ValueError):
                    packager.package(destination, root=root, skill="delivery-triage")
                self.assertFalse(destination.exists())


if __name__ == "__main__":
    unittest.main()
