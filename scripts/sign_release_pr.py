#!/usr/bin/env python3
"""Replace Release Please's unsigned PAT commit with an identical verified commit.

Requires Python 3.9+, GitHub CLI, and GH_TOKEN with repository contents write
and pull requests read access. Run only after the trusted main release job.
"""

import argparse
import base64
import json
import os
import re
import subprocess
import sys
import uuid


RELEASE_BRANCH = "release-please--branches--main--components--ops-triage"
RELEASE_FILES = {".release-please-manifest.json", "CHANGELOG.md", "packaging/plugin.json"}
ZERO_OID = "0" * 40

CREATE_REF = """mutation($input: CreateRefInput!) {
  createRef(input: $input) { ref { id } }
}"""
CREATE_COMMIT = """mutation($input: CreateCommitOnBranchInput!) {
  createCommitOnBranch(input: $input) { commit { oid } }
}"""
UPDATE_REFS = """mutation($input: UpdateRefsInput!) {
  updateRefs(input: $input) { clientMutationId }
}"""
DELETE_REF = """mutation($input: DeleteRefInput!) {
  deleteRef(input: $input) { clientMutationId }
}"""


def gh_api(path, method="GET", payload=None):
    command = ["gh", "api", "--method", method, path]
    if payload is not None:
        command += ["--input", "-"]
    result = subprocess.run(command, input=json.dumps(payload) if payload is not None else None,
                            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode:
        raise RuntimeError(f"GitHub API request failed: {result.stderr.strip()}")
    return json.loads(result.stdout)


def graphql(api, query, inputs):
    result = api("graphql", "POST", {"query": query, "variables": {"input": inputs}})
    if result.get("errors"):
        raise RuntimeError("; ".join(error["message"] for error in result["errors"]))
    return result["data"]


def sign_release_pr(repository, number, api=gh_api):
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        raise ValueError("Expected an owner/repository name")
    prefix = f"repos/{repository}"
    pr = api(f"{prefix}/pulls/{number}")
    if (pr["state"] != "open" or pr["base"]["ref"] != "main"
            or pr["head"]["ref"] != RELEASE_BRANCH
            or not pr["head"]["repo"] or pr["head"]["repo"]["full_name"] != repository
            or pr["base"]["repo"]["full_name"] != repository):
        raise ValueError("Expected the open, same-repository ops-triage release PR against main")

    original = pr["head"]["sha"]
    head = api(f"{prefix}/commits/{original}")
    if pr["commits"] != 1 or len(head["parents"]) != 1:
        raise ValueError("Expected one generated release commit; review additional commits manually")
    files = head["files"]
    if not files or len(files) != pr["changed_files"] or len(files) > len(RELEASE_FILES):
        raise ValueError("The release commit's file list is empty or incomplete")
    for file in files:
        if file["filename"] not in RELEASE_FILES or file["status"] not in {"added", "modified"}:
            raise ValueError(f"Unexpected release change: {file['filename']} ({file['status']})")
    if head["commit"]["verification"]["verified"]:
        print(f"Release PR #{number} already has a verified commit: {original}")
        return original

    additions = []
    for file in files:
        blob = api(f"{prefix}/git/blobs/{file['sha']}")
        if blob["encoding"] != "base64":
            raise ValueError("Expected base64 Git blob contents")
        contents = base64.b64encode(base64.b64decode(blob["content"])).decode("ascii")
        additions.append({"path": file["filename"], "contents": contents})

    parent = head["parents"][0]["sha"]
    repository_id = pr["base"]["repo"]["node_id"]
    temporary = f"refs/heads/release-please-signing/{uuid.uuid4().hex}"
    ref = graphql(api, CREATE_REF, {
        "repositoryId": repository_id, "name": temporary, "oid": parent,
    })["createRef"]["ref"]
    published = False
    try:
        headline, _, body = head["commit"]["message"].partition("\n\n")
        message = {"headline": headline}
        if body:
            message["body"] = body
        signed = graphql(api, CREATE_COMMIT, {
            "branch": {"id": ref["id"]}, "expectedHeadOid": parent,
            "message": message,
            "fileChanges": {"additions": additions},
        })["createCommitOnBranch"]["commit"]["oid"]
        replacement = api(f"{prefix}/commits/{signed}")
        if not replacement["commit"]["verification"]["verified"]:
            raise ValueError("GitHub did not verify the replacement commit; release branch unchanged")
        if (replacement["commit"]["tree"]["sha"] != head["commit"]["tree"]["sha"]
                or replacement["commit"]["message"] != head["commit"]["message"]
                or [p["sha"] for p in replacement["parents"]] != [parent]):
            raise ValueError("Replacement changed the release tree, message or parent; branch unchanged")
        # Replace only the head we inspected. Delete our temporary ref in the
        # same atomic update; concurrent edits make the entire update fail.
        graphql(api, UPDATE_REFS, {
            "repositoryId": repository_id,
            "refUpdates": [
                {"name": f"refs/heads/{RELEASE_BRANCH}", "beforeOid": original,
                 "afterOid": signed, "force": True},
                {"name": temporary, "beforeOid": signed, "afterOid": ZERO_OID},
            ],
        })
        published = True
        print(f"Release PR #{number}: replaced {original} with verified commit {signed}")
        return signed
    finally:
        if not published:
            try:
                graphql(api, DELETE_REF, {"refId": ref["id"]})
            except (RuntimeError, OSError) as error:
                print(f"Could not remove temporary signing branch {temporary}: {error}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", default=os.environ.get("GITHUB_REPOSITORY"), required=False)
    parser.add_argument("--pr", type=int, help="Repair one existing release PR instead of RELEASE_PRS")
    args = parser.parse_args()
    if not args.repository:
        parser.error("Set GITHUB_REPOSITORY or pass --repository")
    try:
        numbers = ([args.pr] if args.pr is not None else
                   [pr["number"] for pr in json.loads(os.environ.get("RELEASE_PRS", "[]"))])
        for number in numbers:
            if not isinstance(number, int) or isinstance(number, bool) or number < 1:
                raise ValueError("Expected a positive release PR number")
            sign_release_pr(args.repository, number)
    except (ValueError, RuntimeError, OSError) as error:
        parser.exit(1, f"Release commit signing failed: {error}\n")


if __name__ == "__main__":
    main()
