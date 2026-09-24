#!/usr/bin/env python3
"""Exercise the real skills CLI in temporary project directories, without cloud access."""

import argparse
import os
from pathlib import Path
import stat
import subprocess
import tempfile


def files(directory):
    return {str(p.relative_to(directory)): (p.read_bytes(), stat.S_IMODE(p.stat().st_mode))
            for p in directory.rglob("*") if p.is_file()
            and "__pycache__" not in p.parts and p.suffix != ".pyc"}


def smoke_install(distribution):
    distribution = Path(distribution).resolve()
    expected = {p.parent.name for p in (distribution / "skills").glob("*/SKILL.md")}
    if not expected:
        raise AssertionError("No skills found in installation source")
    with tempfile.TemporaryDirectory(prefix="ops-skills-install-") as temporary:
        environment = dict(os.environ, DISABLE_TELEMETRY="1", DO_NOT_TRACK="1",
                           npm_config_ignore_scripts="true",
                           XDG_STATE_HOME=str(Path(temporary) / "state"))
        for mode in ("symlink", "copy"):
            project = Path(temporary) / mode
            project.mkdir()
            command = ["npx", "--yes", "skills@1.7.0", "add", str(distribution),
                       "--skill", "*", "--agent", "codex", "claude-code", "--yes"]
            if mode == "copy":
                command.append("--copy")
            subprocess.run(command, cwd=project, env=environment, check=True)
            for agent in (".agents", ".claude"):
                installed = project / agent / "skills"
                actual = {p.name for p in installed.iterdir() if (p / "SKILL.md").is_file()}
                if actual != expected:
                    raise AssertionError(f"{mode}/{agent}: unexpected catalog {actual}")
                for skill in sorted(expected):
                    target = installed / skill
                    if files(target) != files(distribution / "skills" / skill):
                        raise AssertionError(f"Installed files differ: {mode}/{agent}/{skill}")
                    subprocess.run(["skills-ref", "validate", str(target)], check=True,
                                   stdout=subprocess.DEVNULL)
            print(f"{mode}: {len(expected)} complete skills installed and validated for both agents")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("distribution", type=Path, help="Assembled bundle or checkout of the release branch")
    smoke_install(parser.parse_args().distribution)
