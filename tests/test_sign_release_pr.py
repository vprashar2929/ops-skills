"""Exercise verified release replacement and failure paths without GitHub access."""

import base64
import copy
import io
import json
import os
from pathlib import Path
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import sign_release_pr as signer


class FakeGitHub:
    repository = "example/ops-skills"
    original = "a" * 40
    parent = "b" * 40
    signed = "c" * 40
    concurrent = "d" * 40

    def __init__(self):
        repo = {"full_name": self.repository, "node_id": "repository-id"}
        self.pr = {
            "state": "open", "commits": 1, "changed_files": 3,
            "base": {"ref": "main", "repo": repo},
            "head": {"ref": signer.RELEASE_BRANCH, "repo": repo, "sha": self.original},
        }
        self.contents = {
            ".release-please-manifest.json": b'{".": "0.1.5"}\n',
            "packaging/plugin.json": b'{"version": "0.1.5"}\n',
            "CHANGELOG.md": "# Release\r\n\nFix café.\n".encode(),
        }
        self.head = {
            "parents": [{"sha": self.parent}],
            "commit": {"verification": {"verified": False}, "tree": {"sha": "tree"},
                       "message": "chore(main): release ops-triage 0.1.5"},
            "files": [{"filename": name, "status": "modified", "sha": str(i)}
                      for i, name in enumerate(self.contents)],
        }
        self.replacement = copy.deepcopy(self.head)
        self.replacement["commit"]["verification"]["verified"] = True
        self.branch = self.original
        self.temporary = None
        self.mutations = []
        self.commit_input = None
        self.race = False
        self.commit_error = False
        self.cleanup_error = False

    def __call__(self, path, method="GET", payload=None):
        prefix = f"repos/{self.repository}"
        if path == f"{prefix}/pulls/31":
            return copy.deepcopy(self.pr)
        if path == f"{prefix}/commits/{self.original}":
            return copy.deepcopy(self.head)
        if path == f"{prefix}/commits/{self.signed}":
            return copy.deepcopy(self.replacement)
        if path.startswith(f"{prefix}/git/blobs/"):
            data = list(self.contents.values())[int(path.rsplit("/", 1)[1])]
            return {"encoding": "base64", "content": base64.encodebytes(data).decode()}
        if path != "graphql" or method != "POST":
            raise AssertionError(f"Unexpected API call: {path}")
        inputs = payload["variables"]["input"]
        query = payload["query"]
        if "createRef(" in query:
            self.mutations.append("createRef")
            self.temporary = inputs["name"]
            if inputs["oid"] != self.parent:
                raise AssertionError("Signing branch must start at the original parent")
            return {"data": {"createRef": {"ref": {"id": "temporary-id"}}}}
        if "createCommitOnBranch(" in query:
            self.mutations.append("createCommitOnBranch")
            self.commit_input = inputs
            if self.commit_error:
                raise RuntimeError("Commit API unavailable")
            if self.race:
                self.branch = self.concurrent
            return {"data": {"createCommitOnBranch": {"commit": {"oid": self.signed}}}}
        if "updateRefs(" in query:
            self.mutations.append("updateRefs")
            release, temporary = inputs["refUpdates"]
            if release["beforeOid"] != self.branch:
                return {"errors": [{"message": "Reference no longer points to expected head"}]}
            if (release["name"] != f"refs/heads/{signer.RELEASE_BRANCH}"
                    or not release["force"] or temporary["name"] != self.temporary
                    or temporary["beforeOid"] != self.signed
                    or temporary["afterOid"] != signer.ZERO_OID):
                raise AssertionError("Unexpected atomic reference update")
            self.branch = release["afterOid"]
            self.temporary = None
            return {"data": {"updateRefs": {"clientMutationId": None}}}
        if "deleteRef(" in query:
            self.mutations.append("deleteRef")
            if self.cleanup_error:
                raise RuntimeError("Cleanup unavailable")
            self.temporary = None
            return {"data": {"deleteRef": {"clientMutationId": None}}}
        raise AssertionError(f"Unexpected GraphQL mutation: {query}")


class SignReleasePRTests(unittest.TestCase):
    def setUp(self):
        self.github = FakeGitHub()
        output = mock.patch("sys.stdout", new_callable=io.StringIO)
        output.start()
        self.addCleanup(output.stop)

    def sign(self):
        return signer.sign_release_pr(self.github.repository, 31, api=self.github)

    def test_unsigned_release_is_replaced_without_changing_file_bytes(self):
        self.assertEqual(self.sign(), self.github.signed)
        self.assertEqual(self.github.branch, self.github.signed)
        self.assertIsNone(self.github.temporary)
        additions = self.github.commit_input["fileChanges"]["additions"]
        self.assertEqual({file["path"]: base64.b64decode(file["contents"]) for file in additions},
                         self.github.contents)
        self.assertEqual(self.github.commit_input["expectedHeadOid"], self.github.parent)

    def test_already_verified_release_is_not_rewritten(self):
        self.github.head["commit"]["verification"]["verified"] = True
        self.assertEqual(self.sign(), self.github.original)
        self.assertEqual(self.github.mutations, [])

    def test_verified_commit_does_not_bypass_release_file_scope(self):
        self.github.head["commit"]["verification"]["verified"] = True
        self.github.head["files"][0]["filename"] = "unexpected.txt"
        with self.assertRaisesRegex(ValueError, "Unexpected release change"):
            self.sign()
        self.assertEqual(self.github.mutations, [])

    def test_changed_tree_parent_message_or_failed_verification_is_not_published(self):
        for case in ("tree", "parent", "message", "verification"):
            with self.subTest(case=case):
                self.github = FakeGitHub()
                replacement = self.github.replacement
                if case == "tree":
                    replacement["commit"]["tree"]["sha"] = "different-tree"
                elif case == "parent":
                    replacement["parents"] = [{"sha": "unexpected-parent"}]
                elif case == "message":
                    replacement["commit"]["message"] += " changed"
                else:
                    replacement["commit"]["verification"]["verified"] = False
                with self.assertRaises(ValueError):
                    self.sign()
                self.assertEqual(self.github.branch, self.github.original)
                self.assertNotIn("updateRefs", self.github.mutations)
                self.assertIsNone(self.github.temporary)

    def test_concurrent_update_is_preserved_and_temporary_branch_is_removed(self):
        self.github.race = True
        with self.assertRaisesRegex(RuntimeError, "expected head"):
            self.sign()
        self.assertEqual(self.github.branch, self.github.concurrent)
        self.assertIsNone(self.github.temporary)

    def test_api_failure_cleans_up_without_replacing_release_head(self):
        self.github.commit_error = True
        with self.assertRaisesRegex(RuntimeError, "Commit API unavailable"):
            self.sign()
        self.assertEqual(self.github.branch, self.github.original)
        self.assertIsNone(self.github.temporary)

    def test_cleanup_failure_does_not_hide_original_error(self):
        self.github.commit_error = True
        self.github.cleanup_error = True
        with mock.patch("sys.stderr", new_callable=io.StringIO) as errors:
            with self.assertRaisesRegex(RuntimeError, "Commit API unavailable"):
                self.sign()
        self.assertIn("Could not remove temporary signing branch", errors.getvalue())
        self.assertEqual(self.github.branch, self.github.original)

    def test_unexpected_files_changes_or_incomplete_list_are_rejected_before_mutation(self):
        for case in ("path", "deletion", "incomplete", "empty"):
            with self.subTest(case=case):
                self.github = FakeGitHub()
                if case == "path":
                    self.github.head["files"][0]["filename"] = ".github/workflows/unexpected.yml"
                elif case == "deletion":
                    self.github.head["files"][0]["status"] = "removed"
                elif case == "incomplete":
                    self.github.pr["changed_files"] += 1
                else:
                    self.github.head["files"] = []
                with self.assertRaises(ValueError):
                    self.sign()
                self.assertEqual(self.github.mutations, [])

    def test_other_branches_forks_closed_prs_and_multiple_commits_are_rejected(self):
        for case in ("head", "base", "fork", "closed", "commits", "parents"):
            with self.subTest(case=case):
                self.github = FakeGitHub()
                if case in {"head", "base"}:
                    self.github.pr[case]["ref"] = "another-branch"
                elif case == "fork":
                    self.github.pr["head"]["repo"] = {"full_name": "other/fork"}
                elif case == "closed":
                    self.github.pr["state"] = "closed"
                elif case == "commits":
                    self.github.pr["commits"] = 2
                else:
                    self.github.head["parents"].append({"sha": "another-parent"})
                with self.assertRaises(ValueError):
                    self.sign()
                self.assertEqual(self.github.mutations, [])

    def test_action_output_selects_generated_pr_and_empty_output_is_a_noop(self):
        for prs, expected in (([], []), ([{"number": 31}], [mock.call("example/ops-skills", 31)])):
            with self.subTest(prs=prs), mock.patch.dict(os.environ, {
                    "GITHUB_REPOSITORY": "example/ops-skills", "RELEASE_PRS": json.dumps(prs)}), \
                    mock.patch.object(sys, "argv", ["sign_release_pr.py"]), \
                    mock.patch.object(signer, "sign_release_pr") as sign:
                signer.main()
                self.assertEqual(sign.call_args_list, expected)


if __name__ == "__main__":
    unittest.main()
