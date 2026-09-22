#!/usr/bin/env python3
"""Refresh committed references from reviewed submodules, or check them for drift."""

import argparse
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile

from package_skill import ROOT, SKILLS, package, reject_symlinks


def files(directory):
    return {str(p.relative_to(directory)): (p.read_bytes(), stat.S_IMODE(p.stat().st_mode))
            for p in directory.rglob("*") if p.is_file()
            and "__pycache__" not in p.parts and p.suffix != ".pyc"}


def sync_upstream(root=ROOT, *, check=False):
    with tempfile.TemporaryDirectory(prefix="ops-upstream-") as temporary:
        staged = Path(temporary)
        # Validate every refreshed skill before changing any committed references.
        for skill in SKILLS:
            package(staged / skill, root=root, skill=skill, refresh_upstream=True)
        changed = []
        for skill, selections in SKILLS.items():
            references = root / "skills" / skill / "references"
            reject_symlinks(references)
            for label, _, _ in selections:
                source = staged / skill / "references" / label
                target = references / label
                if not target.exists() or files(source) != files(target):
                    changed.append((source, target))
        if check:
            if changed:
                paths = ", ".join(str(target.relative_to(root)) for _, target in changed)
                raise ValueError(f"Upstream references differ: {paths}. Run scripts/sync_upstream.py")
        else:
            for source, target in changed:
                if target.exists():
                    shutil.rmtree(target)
                shutil.copytree(source, target)
        return len(changed)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Fail on drift without changing files")
    args = parser.parse_args()
    try:
        count = sync_upstream(check=args.check)
        print("Upstream references match pinned sources" if args.check else f"Updated {count} reference directories")
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"Upstream sync failed: {error}\n")
