#!/usr/bin/env python3
"""Assemble a portable operational skill using reviewed, pinned upstream guides."""

import argparse
import json
import re
from pathlib import Path
import shutil
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[1]
SUBMODULE = "upstream/google-skills"
SELECTED = "skills/cloud/gke-workload-troubleshooting"

# Explicit selections, not automatic catalog installation. Values are
# (packaged reference directory, submodule path, source skill directory).
def google(label, name):
    return (label, SUBMODULE, "skills/cloud/" + name)


SKILLS = {
    "workload-triage": [("google-gke-workload", SUBMODULE, SELECTED)],
    "service-connectivity-triage": [
        google("google-gke-networking", "gke-networking"),
        ("community-istio", "upstream/wshobson-agents",
         "plugins/cloud-infrastructure/skills/istio-traffic-management"),
    ],
    "gke-cluster-triage": [
        google("google-node-notready", "gke-node-notready"),
        google("google-autoscaler", "gke-cluster-autoscaler"),
        google("google-storage", "gke-storage-troubleshooting"),
    ],
    "observability-triage": [
        google("google-metrics", "cloud-monitoring-metric-selection"),
        google("google-promql", "cloud-monitoring-promql-query"),
        google("google-logging", "cloud-logging-query-generation"),
        ("community-mesh-observability", "upstream/wshobson-agents",
         "plugins/cloud-infrastructure/skills/service-mesh-observability"),
    ],
    "delivery-triage": [],
    "cloud-sql-triage": [
        google("google-metrics", "cloud-monitoring-metric-selection"),
        ("planetscale-mysql", "upstream/planetscale-database-skills", "skills/mysql"),
    ],
    "redis-triage": [
        ("redis-observability", "upstream/redis-skills", "skills/redis-observability"),
        ("redis-connections", "upstream/redis-skills", "skills/redis-connections"),
        ("redis-clustering", "upstream/redis-skills", "skills/redis-clustering"),
    ],
    "cloud-cost-review": [google("google-gke-cost", "gke-cost-analysis")],
    "kafka-triage": [],
}

# Only these diagnostic references are needed; omit the provider-oriented
# entrypoint and its floating main-branch links and schema-design material.
REFERENCE_FILES = {
    "planetscale-mysql": (
        "references/connection-management.md",
        "references/deadlocks.md",
        "references/row-locking-gotchas.md",
        "references/explain-analysis.md",
        "references/replication-lag.md",
    ),
}


def git(root, *args):
    return subprocess.check_output(
        ["git", "-C", str(root), *args], text=True, stderr=subprocess.PIPE
    ).strip()


def reject_symlinks(path):
    if path.is_symlink() or any(p.is_symlink() for p in path.rglob("*")):
        raise ValueError(f"Review symlinks before packaging: {path}")


def checked_revision(root, submodule_path):
    submodule = root / submodule_path
    entry = git(root, "ls-files", "--stage", "--", submodule_path).split()
    if len(entry) != 4 or entry[0] != "160000" or entry[2] != "0":
        raise ValueError("Missing or conflicted submodule gitlink; initialize the recorded submodule")
    revision = git(submodule, "rev-parse", "HEAD")
    if revision != entry[1]:
        raise ValueError("Submodule HEAD differs from recorded gitlink; review and stage its revision first")
    if git(submodule, "status", "--porcelain", "--untracked-files=all"):
        raise ValueError("Upstream checkout has local changes; do not package an edited upstream")
    return revision


def check_links(directory):
    """Check local Markdown destinations; external URLs and anchors are not fetched."""
    for document in directory.rglob("*.md"):
        for link in re.findall(r"\]\(([^\s)]+)(?:\s+[^)]*)?\)", document.read_text()):
            link = link.strip("<>").split("#", 1)[0]
            if not link or re.match(r"[a-zA-Z][a-zA-Z0-9+.-]*:", link):
                continue
            target = (document.parent / link).resolve()
            if not target.is_relative_to(directory.resolve()) or not target.exists():
                raise ValueError(f"Unresolved or escaping link in {document.relative_to(directory)}: {link}")


def package(destination, root=ROOT, skill="workload-triage"):
    if skill not in SKILLS:
        raise ValueError(f"Unknown skill: {skill}")
    destination = Path(destination).absolute()
    if destination.exists() or destination.is_symlink():
        raise ValueError(f"Destination already exists; choose a new directory: {destination}")
    for source in (root / "skills", root / "upstream", root / "scripts", root / "tests", root / ".git"):
        if destination.resolve().is_relative_to(source.resolve()):
            raise ValueError("Destination must be outside source and Git metadata directories")

    selections = SKILLS[skill]
    revisions = {path: checked_revision(root, path) for _, path, _ in selections}
    if destination.name != skill:
        raise ValueError(f"Destination leaf directory must match skill name: {skill}")
    source_skill = root / "skills" / skill
    for source in [source_skill] + [root / path / selected for _, path, selected in selections]:
        if not (source / "SKILL.md").is_file():
            raise ValueError(f"Required skill is missing: {source}")
        reject_symlinks(source)
    for path in revisions:
        for name in ("LICENSE", "NOTICE"):
            if (root / path / name).is_symlink():
                raise ValueError(f"Review upstream {name} symlink before packaging")

    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".ops-skill-", dir=destination.parent) as temporary:
        staged = Path(temporary) / skill
        shutil.copytree(source_skill, staged, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        for label, path, selected in selections:
            submodule = root / path
            vendor = staged / "references" / label
            selected_files = REFERENCE_FILES.get(label)
            if selected_files:
                for relative in selected_files:
                    target = vendor / relative
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(submodule / selected / relative, target)
            else:
                shutil.copytree(submodule / selected, vendor,
                                ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
                # Preserve bytes without exposing a second selectable entrypoint.
                (vendor / "SKILL.md").rename(vendor / "guide.md")
            shutil.copy2(submodule / "LICENSE", vendor / "LICENSE")
            if (submodule / "NOTICE").is_file():
                shutil.copy2(submodule / "NOTICE", vendor / "NOTICE")
            provenance = {
                "repository": git(root, "config", "-f", ".gitmodules", f"submodule.{path}.url").removesuffix(".git"),
                "revision": revisions[path], "path": selected, "modified": False,
                "entrypoint_mapping": {} if selected_files else {"SKILL.md": "guide.md"},
            }
            if selected_files:
                provenance["included_files"] = list(selected_files)
            (vendor / "UPSTREAM.json").write_text(json.dumps(provenance, indent=2) + "\n")
        entrypoints = [p.relative_to(staged) for p in staged.rglob("*")
                       if p.name.lower() == "skill.md"]
        if entrypoints != [Path("SKILL.md")]:
            raise ValueError(f"Bundle must expose only the {skill} SKILL.md; review nested entrypoints")
        check_links(staged)
        # Recheck before publishing so an existing installation is not overwritten.
        if destination.exists() or destination.is_symlink():
            raise ValueError("Destination appeared during packaging; choose a new directory")
        staged.rename(destination)
    return destination


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path, help="New directory with the same name as the skill")
    parser.add_argument("--skill", choices=SKILLS, default="workload-triage")
    args = parser.parse_args()
    try:
        print(package(args.destination, skill=args.skill))
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"Packaging failed: {error}\n")
