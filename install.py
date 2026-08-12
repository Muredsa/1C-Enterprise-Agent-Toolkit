#!/usr/bin/env python3
"""Install the portable skills and shared CLI without third-party packages."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Sequence


PROJECT_ROOT = Path(__file__).resolve().parent
SKILLS_ROOT = PROJECT_ROOT / "skills"
CLI_SOURCE = PROJECT_ROOT / "scripts" / "onec.py"
SKILL_NAMES = (
    "onec-dev",
    "onec-selective-export",
    "onec-extension-lifecycle",
    "onec-extension-validate",
)


class InstallError(RuntimeError):
    pass


def default_skills_target(agent: str) -> Path:
    if agent == "codex":
        return Path.home() / ".codex" / "skills"
    if agent == "claude":
        return Path.home() / ".claude" / "skills"
    raise InstallError(f"Unsupported agent: {agent}")


def default_cli_target() -> Path:
    if os.name == "nt":
        local = os.environ.get("LOCALAPPDATA")
        base = Path(local) if local else Path.home() / "AppData" / "Local"
        return base / "onec-dev-toolkit" / "onec.py"
    return Path.home() / ".local" / "share" / "onec-dev-toolkit" / "onec.py"


def resolved_target(value: str | None, fallback: Path) -> Path:
    return Path(value).expanduser().resolve() if value else fallback.expanduser().resolve()


def install(
    skills_target: Path,
    cli_target: Path,
    *,
    upgrade: bool,
    dry_run: bool,
) -> dict[str, object]:
    sources = [(SKILLS_ROOT / name, skills_target / name) for name in SKILL_NAMES]
    for source, destination in sources:
        if not (source / "SKILL.md").is_file():
            raise InstallError(f"Skill source is incomplete: {source}")
        if destination.exists() and not upgrade:
            raise InstallError(
                f"Skill already exists: {destination}; rerun with --upgrade to overwrite project files"
            )
    if not CLI_SOURCE.is_file():
        raise InstallError(f"Shared CLI is missing: {CLI_SOURCE}")
    if cli_target.exists() and not upgrade:
        raise InstallError(
            f"Shared CLI already exists: {cli_target}; rerun with --upgrade"
        )

    if not dry_run:
        skills_target.mkdir(parents=True, exist_ok=True)
        for source, destination in sources:
            shutil.copytree(source, destination, dirs_exist_ok=upgrade)
        cli_target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(CLI_SOURCE, cli_target)

    return {
        "ok": True,
        "dry_run": dry_run,
        "skills_target": str(skills_target),
        "skills": [str(destination) for _, destination in sources],
        "cli": str(cli_target),
        "next": "Restart the agent and invoke $onec-dev.",
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Install 1C Dev Toolkit Agent Skills and shared CLI"
    )
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--agent", choices=("codex", "claude"))
    target.add_argument("--target", help="Custom Agent Skills directory")
    parser.add_argument("--cli-target", help="Custom destination for onec.py")
    parser.add_argument("--upgrade", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        skills_target = resolved_target(
            args.target,
            default_skills_target(args.agent) if args.agent else Path(args.target),
        )
        cli_target = resolved_target(args.cli_target, default_cli_target())
        result = install(
            skills_target,
            cli_target,
            upgrade=args.upgrade,
            dry_run=args.dry_run,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (InstallError, OSError) as error:
        print(json.dumps({"ok": False, "error": str(error)}, ensure_ascii=False, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
