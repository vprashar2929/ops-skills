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
from plugin_metadata import manifests, package_metadata


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
        package_metadata(Path(__file__).resolve().parents[1] / "packaging", self.bundle)
        self.set_plugin_version("1.2.3")
        self.tag_release()

    def commit_source(self):
        git(self.root, "add", ".")
        git(self.root, "commit", "-m", "source")
        return git(self.root, "rev-parse", "HEAD")

    def write_provenance(self, **changes):
        data = {"commit": self.commit, "dirty": False, "skills": ["example"]}
        data.update(changes)
        (self.bundle / "SOURCE.json").write_text(json.dumps(data))

    def publish(self):
        return publisher.publish(self.bundle, self.commit, self.tag, root=self.root)

    def tag_release(self):
        portable = json.loads((self.bundle / "plugin.json").read_text())
        self.tag = f"{portable['name']}-v{portable['version']}"
        git(self.root, "tag", "--no-sign", self.tag, self.commit)

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
        self.set_plugin_version("1.2.4")
        self.tag_release()
        revision = self.publish()
        self.assertEqual(git(self.remote, "rev-parse", "release^"), previous)
        self.assertEqual(git(self.remote, "rev-parse", "release"), revision)
        self.assertNotIn("old.txt", git(self.remote, "ls-tree", "-r", "--name-only", "release"))
        self.assertEqual(git(self.remote, "show", f"{previous}:skills/example/old.txt"), "old resource")

    def set_plugin_version(self, version):
        portable = json.loads((self.bundle / "plugin.json").read_text())
        portable["version"] = version
        for relative, content in manifests(portable).items():
            (self.bundle / relative).write_text(json.dumps(content, indent=2) + "\n")

    def test_plugin_versions_are_immutable_and_only_greater_versions_ship(self):
        previous = self.publish()
        original_tree = git(self.remote, "rev-parse", "release^{tree}")
        original_source = git(self.remote, "show", "release:SOURCE.json")
        (self.skill / "old.txt").write_text("updated resource")
        (self.bundle / "UPSTREAM.json").write_text('{"revision": "new"}')
        with self.assertRaisesRegex(ValueError, "without a version bump"):
            self.publish()
        self.assertEqual(git(self.remote, "rev-parse", "release^{tree}"), original_tree)
        self.assertEqual(git(self.remote, "show", "release:SOURCE.json"), original_source)
        self.set_plugin_version("1.2.2")
        self.tag_release()
        with self.assertRaisesRegex(ValueError, "must not decrease"):
            self.publish()
        self.assertEqual(git(self.remote, "rev-parse", "release"), previous)
        (self.root / "authored.txt").write_text("updated source\n")
        self.commit = self.commit_source()
        git(self.root, "push", "origin", "main")
        self.write_provenance()
        self.set_plugin_version("1.2.4")
        self.tag_release()
        revision = self.publish()
        self.assertNotEqual(revision, previous)
        self.assertEqual(git(self.remote, "rev-parse", "release^"), previous)
        for path in self.bundle.rglob("*"):
            if path.is_file():
                content = subprocess.check_output(["git", "-C", str(self.remote), "show",
                    f"release:{path.relative_to(self.bundle)}"])
                self.assertEqual(content, path.read_bytes())
        self.assertEqual(self.publish(), revision)
        (self.skill / "old.txt").write_text("retry with different bytes")
        with self.assertRaisesRegex(ValueError, "without a version bump"):
            self.publish()
        self.assertEqual(git(self.remote, "show", "release:skills/example/old.txt"), "updated resource")

    def test_concurrent_publisher_cannot_overwrite_release(self):
        previous = self.publish()
        self.set_plugin_version("1.2.4")
        self.tag_release()
        (self.skill / "new.txt").write_text("new resource")
        competing = None

        def race(directory, *args):
            nonlocal competing
            if args == ("push", "origin", "HEAD:refs/heads/release"):
                tree = git(self.remote, "rev-parse", "release^{tree}")
                competing = git(self.root, "commit-tree", tree, "-p", previous, "-m", "competing publisher")
                git(self.root, "push", "origin", f"{competing}:refs/heads/release")
            return git(directory, *args)

        with mock.patch.object(publisher, "git", side_effect=race):
            with self.assertRaises(subprocess.CalledProcessError):
                self.publish()
        self.assertEqual(git(self.remote, "rev-parse", "release"), competing)
        self.assertEqual(git(self.remote, "rev-parse", "release^"), previous)

    def test_plugin_publication_refuses_inconsistent_host_metadata(self):
        previous = self.publish()
        path = self.bundle / ".claude-plugin/plugin.json"
        value = json.loads(path.read_text())
        value["version"] = "999.0.0"
        path.write_text(json.dumps(value))
        with self.assertRaisesRegex(ValueError, "metadata differs"):
            self.publish()
        self.assertEqual(git(self.remote, "rev-parse", "release"), previous)

    def test_tagged_release_stays_pinned_when_main_advances(self):
        self.publish()
        self.set_plugin_version("1.2.4")
        (self.root / "authored.txt").write_text("approved release\n")
        self.commit = self.commit_source()
        git(self.root, "push", "origin", "main")
        self.write_provenance()
        approved = self.commit
        self.tag_release()
        snapshot = self.directory / "approved-bundle"
        shutil.copytree(self.bundle, snapshot)
        (self.root / "authored.txt").write_text("later feature\n")
        self.commit = self.commit_source()
        git(self.root, "push", "origin", "main")
        self.write_provenance()
        (self.skill / "old.txt").write_text("later unapproved feature")
        with self.assertRaisesRegex(ValueError, "does not match the validated source"):
            self.publish()
        revision = publisher.publish(snapshot, approved, self.tag, root=self.root)
        self.assertEqual(json.loads(git(self.remote, "show", "release:SOURCE.json"))["commit"], approved)
        self.assertEqual(git(self.remote, "show", "release:skills/example/old.txt"), "old resource")
        self.assertEqual(publisher.publish(snapshot, approved, self.tag, root=self.root), revision)
        self.assertEqual(git(self.remote, "rev-parse", "release"), revision)

    def test_release_rejects_untrusted_source_or_wrong_tag(self):
        self.set_plugin_version("1.2.4")
        with self.assertRaisesRegex(ValueError, "does not match the plugin"):
            self.publish()
        git(self.root, "checkout", "-b", "untrusted")
        (self.root / "authored.txt").write_text("unmerged branch\n")
        self.commit = self.commit_source()
        self.write_provenance()
        self.tag_release()
        with self.assertRaisesRegex(ValueError, "not an ancestor"):
            self.publish()
        self.assertEqual(git(self.remote, "branch", "--list", "release"), "")

    def test_moved_tag_cannot_replace_a_version_published_from_another_source(self):
        previous = self.publish()
        (self.root / "authored.txt").write_text("different source\n")
        self.commit = self.commit_source()
        git(self.root, "push", "origin", "main")
        self.write_provenance()
        git(self.root, "tag", "--no-sign", "--force", self.tag, self.commit)
        with self.assertRaisesRegex(ValueError, "different source"):
            self.publish()
        self.assertEqual(git(self.remote, "rev-parse", "release"), previous)

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

    def test_main_advancing_during_publication_does_not_replace_tagged_source(self):
        self.publish()
        self.set_plugin_version("1.2.4")
        self.tag_release()
        (self.skill / "new.txt").write_text("new resource")

        def advance_main(directory, *args):
            if args == ("push", "origin", "HEAD:refs/heads/release"):
                (self.root / "authored.txt").write_text("newer source\n")
                self.commit_source()
                git(self.root, "push", "origin", "main")
            return git(directory, *args)

        with mock.patch.object(publisher, "git", side_effect=advance_main):
            self.publish()
        self.assertEqual(json.loads(git(self.remote, "show", "release:SOURCE.json"))["commit"], self.commit)

    def test_cli_reports_remote_rejection_and_preserves_release(self):
        previous = self.publish()
        scripts = self.root / "scripts"
        scripts.mkdir()
        for name in ("publish_distribution.py", "package_skill.py", "plugin_metadata.py"):
            shutil.copy2(Path(publisher.__file__).parent / name, scripts / name)
        self.commit = self.commit_source()
        git(self.root, "push", "origin", "main")
        self.write_provenance()
        self.set_plugin_version("1.2.4")
        self.tag_release()
        (self.skill / "new.txt").write_text("new resource")
        hook = self.remote / "hooks/pre-receive"
        hook.write_text('#!/bin/sh\necho "Release push rejected by fixture policy" >&2\nexit 1\n')
        hook.chmod(0o755)

        result = subprocess.run(
            [sys.executable, str(scripts / "publish_distribution.py"),
             str(self.bundle), "--source-commit", self.commit, "--release-tag", self.tag],
            text=True, capture_output=True)

        self.assertEqual(result.returncode, 1)
        self.assertIn("Release push rejected by fixture policy", result.stderr)
        self.assertEqual(git(self.remote, "rev-parse", "release"), previous)
        self.assertEqual(git(self.root, "worktree", "list", "--porcelain").count("worktree "), 1)


if __name__ == "__main__":
    unittest.main()
