"""Exercise publication against a local bare remote, without GitHub credentials."""

import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import publish_distribution as publisher
from package_skill import git


class PublishTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.root = self.directory / "source"
        self.remote = self.directory / "remote.git"
        git(self.directory, "init", "-b", "main", str(self.root))
        git(self.root, "config", "user.name", "Fixture")
        git(self.root, "config", "user.email", "fixture@example.invalid")
        git(self.root, "config", "commit.gpgsign", "false")
        (self.root / "authored.txt").write_text("source only\n")
        self.commit = self.commit_source()
        git(self.directory, "clone", "--bare", str(self.root), str(self.remote))
        git(self.root, "remote", "add", "origin", str(self.remote))
        self.bundle = self.directory / "bundle"
        self.skill = self.bundle / "skills" / "example"
        self.skill.mkdir(parents=True)
        (self.skill / "SKILL.md").write_text("---\nname: example\ndescription: Test fixture.\n---\n")
        (self.skill / "old.txt").write_text("old resource")
        self.write_provenance()

    def commit_source(self):
        git(self.root, "add", ".")
        git(self.root, "commit", "-m", "source")
        return git(self.root, "rev-parse", "HEAD")

    def write_provenance(self, **changes):
        data = {"commit": self.commit, "dirty": False, "skills": ["example"]}
        data.update(changes)
        (self.bundle / "SOURCE.json").write_text(json.dumps(data))

    def publish(self):
        return publisher.publish(self.bundle, self.commit, root=self.root)

    def test_initial_publication_and_retry_leave_source_untouched(self):
        revision = self.publish()
        self.assertEqual(git(self.remote, "rev-parse", "release"), revision)
        self.assertEqual(git(self.remote, "rev-list", "--count", "release"), "1")
        self.assertEqual(git(self.remote, "show", "release:skills/example/old.txt"), "old resource")
        self.assertNotIn("authored.txt", git(self.remote, "ls-tree", "--name-only", "release"))
        self.assertEqual(self.publish(), revision)
        self.assertEqual(git(self.root, "rev-parse", "HEAD"), self.commit)
        self.assertEqual(git(self.root, "status", "--porcelain"), "")
        self.assertEqual(git(self.root, "branch", "--format=%(refname:short)"), "main")
        self.assertEqual((self.root / "authored.txt").read_text(), "source only\n")

    def test_update_removes_old_files_and_keeps_previous_version(self):
        previous = self.publish()
        (self.root / "authored.txt").write_text("updated source\n")
        self.commit = self.commit_source()
        git(self.root, "push", "origin", "main")
        self.write_provenance()
        (self.skill / "old.txt").unlink()
        (self.skill / "new.txt").write_text("new resource")
        revision = self.publish()
        self.assertEqual(git(self.remote, "rev-parse", "release^"), previous)
        self.assertEqual(git(self.remote, "rev-parse", "release"), revision)
        self.assertNotIn("old.txt", git(self.remote, "ls-tree", "-r", "--name-only", "release"))
        self.assertEqual(git(self.remote, "show", f"{previous}:skills/example/old.txt"), "old resource")

    def test_publication_keeps_validated_files_despite_gitignore(self):
        (self.skill / ".gitignore").write_text("old.txt\n")
        self.publish()
        paths = git(self.remote, "ls-tree", "-r", "--name-only", "release").splitlines()
        self.assertIn("skills/example/old.txt", paths)
        self.assertEqual(git(self.remote, "show", "release:skills/example/old.txt"), "old resource")

    def test_publication_refuses_git_transformations_of_validated_bytes(self):
        (self.skill / ".gitattributes").write_text("old.txt text eol=lf\n")
        (self.skill / "old.txt").write_bytes(b"validated resource\r\n")
        with self.assertRaisesRegex(ValueError, "Git staging changed"):
            self.publish()
        self.assertEqual(git(self.remote, "branch", "--list", "release"), "")
        self.assertEqual(git(self.root, "worktree", "list", "--porcelain").count("worktree "), 1)

    def test_refuses_dirty_or_wrong_source_bundle(self):
        for changes in ({"dirty": True}, {"commit": "0" * 40}):
            with self.subTest(changes=changes):
                self.write_provenance(**changes)
                with self.assertRaisesRegex(ValueError, "expected clean source"):
                    self.publish()
        self.assertEqual(git(self.remote, "branch", "--list", "release"), "")

    def test_stale_build_cannot_replace_current_release(self):
        previous = self.publish()
        (self.root / "authored.txt").write_text("newer source\n")
        self.commit_source()
        git(self.root, "push", "origin", "main")
        self.assertIsNone(self.publish())
        self.assertEqual(git(self.remote, "rev-parse", "release"), previous)

    def test_failed_push_keeps_previous_release_and_cleans_worktree(self):
        previous = self.publish()
        (self.skill / "new.txt").write_text("new resource")

        def failing_push(directory, *args):
            if args[0] == "push":
                raise subprocess.CalledProcessError(1, ["git", *args])
            return git(directory, *args)

        with mock.patch.object(publisher, "git", side_effect=failing_push):
            with self.assertRaises(subprocess.CalledProcessError):
                self.publish()
        self.assertEqual(git(self.remote, "rev-parse", "release"), previous)
        self.assertEqual(git(self.root, "worktree", "list", "--porcelain").count("worktree "), 1)

    def test_main_advancing_during_publication_keeps_previous_release(self):
        previous = self.publish()
        (self.skill / "new.txt").write_text("new resource")
        main_fetches = 0

        def advance_main(directory, *args):
            nonlocal main_fetches
            if args == ("fetch", "origin", "refs/heads/main"):
                main_fetches += 1
                if main_fetches == 2:
                    (self.root / "authored.txt").write_text("newer source\n")
                    self.commit_source()
                    git(self.root, "push", "origin", "main")
            return git(directory, *args)

        with mock.patch.object(publisher, "git", side_effect=advance_main):
            self.assertIsNone(self.publish())
        self.assertEqual(git(self.remote, "rev-parse", "release"), previous)

    def test_cli_reports_remote_rejection_and_preserves_release(self):
        previous = self.publish()
        scripts = self.root / "scripts"
        scripts.mkdir()
        for name in ("publish_distribution.py", "package_skill.py"):
            shutil.copy2(Path(publisher.__file__).parent / name, scripts / name)
        self.commit = self.commit_source()
        git(self.root, "push", "origin", "main")
        self.write_provenance()
        (self.skill / "new.txt").write_text("new resource")
        hook = self.remote / "hooks/pre-receive"
        hook.write_text('#!/bin/sh\necho "Release push rejected by fixture policy" >&2\nexit 1\n')
        hook.chmod(0o755)

        result = subprocess.run(
            [sys.executable, str(scripts / "publish_distribution.py"),
             str(self.bundle), "--source-commit", self.commit],
            text=True, capture_output=True)

        self.assertEqual(result.returncode, 1)
        self.assertIn("Release push rejected by fixture policy", result.stderr)
        self.assertEqual(git(self.remote, "rev-parse", "release"), previous)
        self.assertEqual(git(self.root, "worktree", "list", "--porcelain").count("worktree "), 1)


if __name__ == "__main__":
    unittest.main()
