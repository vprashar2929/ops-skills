"""Generate host metadata around one portable, skills-only plugin payload."""

import json
from pathlib import Path
import re


MARKETPLACE = "ops-skills"
SCHEMA_URL = "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
IDENTITY_FIELDS = ("name", "version", "description", "author", "homepage", "repository", "license")


def release_version(value):
    """This repository publishes three-part numeric release versions."""
    if not isinstance(value, str) or not re.fullmatch(r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)", value):
        raise ValueError("Plugin version must be a three-part numeric release version")
    return tuple(map(int, value.split(".")))


def manifests(portable):
    if portable.get("$schema") != SCHEMA_URL:
        raise ValueError("Portable plugin must declare the Agent Plugins 1.0.0 schema")
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", portable.get("name", "")):
        raise ValueError("Plugin name must use kebab-case")
    release_version(portable.get("version"))
    if not portable.get("description") or not portable.get("author", {}).get("name"):
        raise ValueError("Plugin description and publisher name are required")
    claude = {key: portable[key] for key in IDENTITY_FIELDS if key in portable}
    entry = {"name": portable["name"], "description": portable["description"]}
    return {
        "plugin.json": portable,
        ".claude-plugin/plugin.json": claude,
        ".claude-plugin/marketplace.json": {
            "name": MARKETPLACE,
            "owner": portable["author"],
            "description": "Skills for Kubernetes and Google Cloud operational diagnosis.",
            "plugins": [{**entry, "source": "./"}],
        },
        ".agents/plugins/marketplace.json": {
            "name": MARKETPLACE,
            "interface": {"displayName": "Ops Skills"},
            "plugins": [{**entry, "source": {"source": "local", "path": "./"},
                         "policy": {"installation": "AVAILABLE", "authentication": "ON_USE"},
                         "category": "Developer Tools"}],
        },
    }


def check_metadata(directory):
    directory = Path(directory)
    portable = json.loads((directory / "plugin.json").read_text())
    for relative, expected in manifests(portable).items():
        if json.loads((directory / relative).read_text()) != expected:
            raise ValueError(f"Generated plugin metadata differs: {relative}")


def package_metadata(source, destination):
    source, destination = Path(source), Path(destination)
    if source.is_symlink() or (source / "plugin.json").is_symlink():
        raise ValueError("Review packaging metadata symlinks before packaging")
    portable = json.loads((source / "plugin.json").read_text())
    for relative, content in manifests(portable).items():
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(content, indent=2) + "\n")
    check_metadata(destination)


def check_version_upgrade(previous, incoming):
    """Changing a cached plugin requires a new, increasing version."""
    previous, incoming = Path(previous), Path(incoming)
    if not (previous / "plugin.json").is_file():
        return  # First plugin publication over a legacy skills-only distribution.
    old = json.loads((previous / "plugin.json").read_text())
    new = json.loads((incoming / "plugin.json").read_text())
    if old["name"] != new["name"]:
        raise ValueError("Changing the published plugin identity requires a migration")
    before, after = release_version(old["version"]), release_version(new["version"])
    if after < before:
        raise ValueError("Plugin version must not decrease; publish a rollback as a new version")

    def payload(root):
        return {str(path.relative_to(root)): (path.read_bytes(), bool(path.stat().st_mode & 0o111))
                for path in root.rglob("*") if path.is_file()
                and path.name != ".git" and path.relative_to(root) != Path("SOURCE.json")}

    if after == before and payload(previous) != payload(incoming):
        raise ValueError("Plugin payload changed without a version bump in packaging/plugin.json")
