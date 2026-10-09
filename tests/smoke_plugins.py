#!/usr/bin/env python3
"""Check native Git marketplace installation and one cached update in both CLIs."""

import argparse
import json
import os
from pathlib import Path
import queue
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from package_skill import check_links
from plugin_metadata import MARKETPLACE, manifests
from smoke_install import files


def run(command, project, environment):
    executable = shutil.which(command[0], path=environment["PATH"])
    if executable is None:
        raise AssertionError(f"Missing executable: {command[0]}")
    result = subprocess.run([executable, *command[1:]], cwd=project, env=environment, capture_output=True,
                            text=True, timeout=60)
    if result.returncode:
        raise AssertionError(f"{' '.join(command)} failed:\n{result.stdout}\n{result.stderr}")
    return result.stdout


def codex_skills(project, environment):
    """Use the CLI's own scanner; this does not start a model turn."""
    process = subprocess.Popen([shutil.which("codex", path=environment["PATH"]), "app-server", "--stdio"], cwd=project, env=environment,
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.DEVNULL, text=True)
    output = queue.Queue()

    def reader():
        for line in process.stdout:
            output.put(json.loads(line))
        output.put(None)

    thread = threading.Thread(target=reader, daemon=True)
    thread.start()

    def request(identifier, method, params):
        process.stdin.write(json.dumps({"id": identifier, "method": method, "params": params}) + "\n")
        process.stdin.flush()
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            message = output.get(timeout=max(0.1, deadline - time.monotonic()))
            if message is None:
                raise AssertionError("Codex app-server closed before skill discovery completed")
            if message.get("id") == identifier:
                if "error" in message:
                    raise AssertionError(f"Codex {method}: {message['error']}")
                return message["result"]
        raise AssertionError("Codex skill discovery timed out")

    try:
        request(1, "initialize", {"clientInfo": {"name": "ops-plugin-smoke", "version": "1.0.0"},
                                  "capabilities": {"experimentalApi": True}})
        process.stdin.write('{"method":"initialized"}\n')
        process.stdin.flush()
        return request(2, "skills/list", {"cwds": [str(project)], "forceReload": True})
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        thread.join(timeout=5)
        process.stdin.close()
        process.stdout.close()


def verify_install(host, bundle, project, environment):
    portable = json.loads((bundle / "plugin.json").read_text())
    name, version = portable["name"], portable["version"]
    selector = f"{name}@{MARKETPLACE}"
    expected = {path.parent.name for path in (bundle / "skills").glob("*/SKILL.md")}
    if host == "codex":
        installed = json.loads(run(["codex", "plugin", "add", selector, "--json"], project, environment))
        target = Path(installed["installedPath"])
        if installed["version"] != version:
            raise AssertionError("Codex installed a stale plugin version")
        inventory = codex_skills(project, environment)
        entries = [skill for item in inventory["data"] for skill in item["skills"]
                   if skill.get("pluginId") == selector]
        actual = {entry["name"] for entry in entries}
        if actual != {f"{name}:{skill}" for skill in expected} or len(entries) != len(expected):
            raise AssertionError(f"Codex skill inventory differs: {actual}")
        if not all(entry["enabled"] for entry in entries):
            raise AssertionError("Codex did not enable every plugin skill")
        if any(item["errors"] for item in inventory["data"]):
            raise AssertionError("Codex reported skill loading errors")
        if any(not Path(entry["path"]).resolve().is_relative_to(target.resolve()) for entry in entries):
            raise AssertionError("Codex loaded skills outside its installed plugin")
    else:
        installed = json.loads(run(["claude", "plugin", "list", "--json"], project, environment))
        entries = [entry for entry in installed if entry["id"] == selector]
        if len(entries) != 1 or entries[0]["version"] != version or not entries[0]["enabled"]:
            raise AssertionError(f"Claude installed a stale or disabled plugin: {entries}")
        target = Path(entries[0]["installPath"])
        details = run(["claude", "plugin", "details", name], project, environment)
        count = re.search(r"Skills\s*\((\d+)\)", details)
        if not count or int(count.group(1)) != len(expected) or not all(skill in details for skill in expected):
            raise AssertionError(f"Claude skill inventory differs:\n{details}")
    actual = {path.parent.name for path in (target / "skills").glob("*/SKILL.md")}
    if actual != expected:
        raise AssertionError(f"{host}: installed skill catalog differs")
    for skill in expected:
        if files(target / "skills" / skill) != files(bundle / "skills" / skill):
            raise AssertionError(f"{host}: installed skill bytes or permissions differ: {skill}")
        run(["skills-ref", "validate", str(target / "skills" / skill)], project, environment)
        check_links(target / "skills" / skill)
    for relative in ("plugin.json", ".claude-plugin/plugin.json"):
        if (target / relative).read_bytes() != (bundle / relative).read_bytes():
            raise AssertionError(f"{host}: installed metadata or asset changed: {relative}")
    print(f"{host}: {len(expected)} skills discovered; version {version}, files, permissions and formats verified")
    return target


def environment_at(root, remote):
    root.mkdir(parents=True)
    for name in ("codex", "claude"):
        (root / name).mkdir()
    environment = dict(os.environ, CODEX_HOME=str(root / "codex"), CLAUDE_CONFIG_DIR=str(root / "claude"),
                       DISABLE_AUTOUPDATER="1", DISABLE_TELEMETRY="1", DISABLE_ERROR_REPORTING="1",
                       CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC="1")
    # Exercise each CLI's Git source/ref path using a local bare remote.
    environment.update(GIT_CONFIG_COUNT="1", GIT_CONFIG_KEY_0=f"url.{remote.as_uri()}.insteadOf",
                       GIT_CONFIG_VALUE_0="https://example.invalid/ops-skills.git")
    return environment


def smoke_plugins(distribution):
    distribution = Path(distribution).resolve()
    identity = json.loads((distribution / "plugin.json").read_text())
    selector = f"{identity['name']}@{MARKETPLACE}"
    with tempfile.TemporaryDirectory(prefix="ops-native-install-") as temporary:
        root = Path(temporary).resolve()
        project = root / "project"
        project.mkdir()
        remote = root / "remote.git"
        environment = environment_at(root / "config", remote)
        for host in ("codex", "claude"):
            print(run([host, "--version"], project, environment).strip())
        for relative in (".claude-plugin/plugin.json", ".claude-plugin/marketplace.json"):
            run(["claude", "plugin", "validate", str(distribution / relative), "--strict"], project, environment)
        fixture = root / "fixture"
        shutil.copytree(distribution, fixture)
        run(["git", "init", "-b", "release", str(fixture)], project, environment)
        for key, value in (("user.name", "Fixture"), ("user.email", "fixture@example.invalid"), ("commit.gpgsign", "false")):
            run(["git", "-C", str(fixture), "config", key, value], project, environment)
        run(["git", "-C", str(fixture), "add", "."], project, environment)
        run(["git", "-C", str(fixture), "commit", "-m", "initial"], project, environment)
        run(["git", "clone", "--bare", str(fixture), str(remote)], project, environment)
        run(["codex", "plugin", "marketplace", "add", "https://example.invalid/ops-skills.git", "--ref", "release", "--json"], project, environment)
        run(["claude", "plugin", "marketplace", "add", "https://example.invalid/ops-skills.git#release"], project, environment)
        run(["claude", "plugin", "install", selector], project, environment)
        for host in ("codex", "claude"):
            verify_install(host, fixture, project, environment)

        # The input bundle remains untouched and recoverable; only the fixture changes.
        major, minor, patch = map(int, identity["version"].split("."))
        portable = dict(identity, version=f"{major}.{minor}.{patch + 1}")
        for relative, content in manifests(portable).items():
            (fixture / relative).write_text(json.dumps(content, indent=2) + "\n")
        skill = fixture / "skills/workload-triage/SKILL.md"
        skill.write_text(skill.read_text() + "\nSynthetic cache update fixture.\n")
        run(["git", "-C", str(fixture), "add", "."], project, environment)
        run(["git", "-C", str(fixture), "commit", "-m", "fixture update"], project, environment)
        run(["git", "-C", str(fixture), "push", str(remote), "release"], project, environment)
        run(["codex", "plugin", "marketplace", "upgrade", MARKETPLACE, "--json"], project, environment)
        run(["claude", "plugin", "marketplace", "update", MARKETPLACE], project, environment)
        run(["claude", "plugin", "update", selector], project, environment)
        for host in ("codex", "claude"):
            verify_install(host, fixture, project, environment)
        print("Both CLIs: Git installation, skill discovery and cached update passed")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("distribution", type=Path)
    smoke_plugins(parser.parse_args().distribution)
