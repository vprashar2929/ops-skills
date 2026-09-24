#!/usr/bin/env python3
"""Publish an already validated bundle to release; never modify the source checkout."""

import argparse
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

from package_skill import ROOT, git, reject_symlinks


def verify_staged_bundle(checkout, bundle):
    """Git ignore rules and attributes must not change the validated payload."""
    expected = {}
    for path in bundle.rglob("*"):
        if path.is_file():
            mode = "100755" if path.stat().st_mode & 0o111 else "100644"
            expected[str(path.relative_to(bundle))] = (
                mode, git(checkout, "hash-object", "--no-filters", "--", str(path)))
    staged = {}
    for entry in git(checkout, "ls-files", "--stage", "-z").split("\0"):
        if entry:
            metadata, name = entry.split("\t", 1)
            mode, digest, stage = metadata.split()
            staged[name] = (mode, digest)
    if staged != expected:
        raise ValueError("Git staging changed the validated bundle; review Git attributes and file modes")


def publish(bundle, source_commit, root=ROOT):
    bundle = Path(bundle).resolve()
    reject_symlinks(bundle)
    if any(p.name == ".git" for p in bundle.rglob("*")):
        raise ValueError("Distribution must not contain Git metadata")
    provenance = json.loads((bundle / "SOURCE.json").read_text())
    if provenance["commit"] != source_commit or provenance["dirty"] is not False:
        raise ValueError("Bundle must come from the expected clean source commit")

    # Only trusted main builds call this script. PR artifacts are never published.
    git(root, "fetch", "origin", "refs/heads/main")
    if git(root, "rev-parse", "FETCH_HEAD") != source_commit:
        print("Skipping publication: main has advanced beyond this build")
        return None
    remote_release = git(root, "ls-remote", "--heads", "origin", "refs/heads/release")
    if remote_release:
        git(root, "fetch", "origin", "refs/heads/release")
        parent = git(root, "rev-parse", "FETCH_HEAD")
    else:
        parent = source_commit

    with tempfile.TemporaryDirectory(prefix="ops-publish-") as temporary:
        checkout = Path(temporary) / "release"
        branch = Path(temporary).name
        git(root, "worktree", "add", "--detach", str(checkout), parent)
        try:
            if not remote_release:
                git(checkout, "checkout", "--orphan", branch)
            git(checkout, "rm", "-r", "-f", "--ignore-unmatch", ".")
            shutil.copytree(bundle, checkout, dirs_exist_ok=True)
            git(checkout, "add", "--force", "--all")
            verify_staged_bundle(checkout, bundle)
            if not git(checkout, "diff", "--cached", "--name-only"):
                print("Distribution is already current")
                return parent
            git(checkout, "-c", "user.name=github-actions[bot]",
                "-c", "user.email=41898282+github-actions[bot]@users.noreply.github.com",
                "-c", "commit.gpgsign=false", "commit", "-m",
                f"build: publish skills from {source_commit}")
            revision = git(checkout, "rev-parse", "HEAD")
            git(root, "fetch", "origin", "refs/heads/main")
            if git(root, "rev-parse", "FETCH_HEAD") != source_commit:
                print("Skipping publication: main advanced during publication")
                return None
            # No force push: a concurrent publisher must not overwrite a newer release.
            git(checkout, "push", "origin", "HEAD:refs/heads/release")
            print(f"Published distribution {revision} from {source_commit}")
            return revision
        finally:
            git(root, "worktree", "remove", "--force", str(checkout))
            if not remote_release and git(root, "branch", "--list", branch):
                git(root, "branch", "-D", branch)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path, help="Extracted, validated distribution")
    parser.add_argument("--source-commit", required=True)
    args = parser.parse_args()
    try:
        publish(args.bundle, args.source_commit)
    except subprocess.CalledProcessError as error:
        parser.exit(1, f"Publication failed: {error}\n{error.stderr or ''}")
    except (ValueError, OSError) as error:
        parser.exit(1, f"Publication failed: {error}\n")
