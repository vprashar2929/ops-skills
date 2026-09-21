#!/usr/bin/env python3
"""Assemble one self-contained skill from the recorded Google submodule revision."""

import argparse
import json
from pathlib import Path
import shutil
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[1]
SUBMODULE = "upstream/google-skills"
SELECTED = "skills/cloud/gke-workload-troubleshooting"


def git(root, *args):
    return subprocess.check_output(
        ["git", "-C", str(root), *args], text=True, stderr=subprocess.PIPE
    ).strip()


def reject_symlinks(path):
    if path.is_symlink() or any(p.is_symlink() for p in path.rglob("*")):
        raise ValueError(f"Review symlinks before packaging: {path}")


def package(destination, root=ROOT):
    destination = Path(destination).absolute()
    if destination.exists() or destination.is_symlink():
        raise ValueError(f"Destination already exists; choose a new directory: {destination}")
    for source in (root / "skills", root / "upstream", root / "scripts", root / "tests", root / ".git"):
        if destination.resolve().is_relative_to(source.resolve()):
            raise ValueError("Destination must be outside source and Git metadata directories")

    submodule = root / SUBMODULE
    entry = git(root, "ls-files", "--stage", "--", SUBMODULE).split()
    if len(entry) != 4 or entry[0] != "160000" or entry[2] != "0":
        raise ValueError("Missing or conflicted submodule gitlink; initialize the recorded submodule")
    revision = git(submodule, "rev-parse", "HEAD")
    if revision != entry[1]:
        raise ValueError("Submodule HEAD differs from recorded gitlink; review and stage its revision first")
    if git(submodule, "status", "--porcelain", "--untracked-files=all"):
        raise ValueError("Upstream checkout has local changes; do not package an edited upstream")

    source_skill = root / "skills/workload-triage"
    selected = submodule / SELECTED
    for source in (source_skill, selected):
        if not (source / "SKILL.md").is_file():
            raise ValueError(f"Required skill is missing: {source}")
        reject_symlinks(source)
    for name in ("LICENSE", "NOTICE"):
        if (submodule / name).is_symlink():
            raise ValueError(f"Review upstream {name} symlink before packaging")

    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".workload-skill-", dir=destination.parent) as temporary:
        staged = Path(temporary) / "workload-triage"
        shutil.copytree(source_skill, staged, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        vendor = staged / "references/google-gke-workload"
        shutil.copytree(selected, vendor)
        # Keep upstream bytes intact without registering another selectable skill.
        (vendor / "SKILL.md").rename(vendor / "guide.md")
        entrypoints = [p.relative_to(staged) for p in staged.rglob("*")
                       if p.name.lower() == "skill.md"]
        if entrypoints != [Path("SKILL.md")]:
            raise ValueError("Bundle must expose only the workload-triage SKILL.md; review nested entrypoints")
        shutil.copy2(submodule / "LICENSE", vendor / "LICENSE")
        if (submodule / "NOTICE").is_file():
            shutil.copy2(submodule / "NOTICE", vendor / "NOTICE")
        (vendor / "UPSTREAM.json").write_text(json.dumps({
            "repository": "https://github.com/google/skills",
            "revision": revision,
            "path": SELECTED,
            "modified": False,
            "entrypoint_mapping": {"SKILL.md": "guide.md"},
        }, indent=2) + "\n")
        # Recheck before publishing so an existing installation is not overwritten.
        if destination.exists() or destination.is_symlink():
            raise ValueError("Destination appeared during packaging; choose a new directory")
        staged.rename(destination)
    return destination


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path, help="New directory to contain the complete workload-triage skill")
    args = parser.parse_args()
    try:
        print(package(args.destination))
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"Packaging failed: {error}\n")
