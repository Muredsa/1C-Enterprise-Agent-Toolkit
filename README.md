# 1C:Enterprise Agent Toolkit

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![CI](https://github.com/Muredsa/1C-Enterprise-Agent-Toolkit/actions/workflows/ci.yml/badge.svg)](https://github.com/Muredsa/1C-Enterprise-Agent-Toolkit/actions/workflows/ci.yml)

[Русская версия](README.ru.md)

A portable Agent Skills project for precise 1C:Enterprise configuration inspection and configuration-extension development. It exports only explicitly selected metadata, keeps extension work out of the main configuration, validates Designer logs as well as exit codes, and removes session-owned working data when finished.

## What is included

- `onec-dev` — safety and workflow router.
- `onec-selective-export` — minimal `/DumpConfigToFiles -listFile` exports.
- `onec-extension-lifecycle` — create, dump, load, back up, roll back, and delete one extension.
- `onec-extension-validate` — syntax, full, applicability, update, and `.cfe` verification gates.
- `scripts/onec.py` — dependency-free Python wrapper around 1C Designer batch mode.
- Codex and Claude Code plugin manifests.

The skills use the open Agent Skills directory convention (`skills/<name>/SKILL.md`). The repository also follows the official Claude plugin layout demonstrated by Anthropic's [example plugin](https://github.com/anthropics/claude-plugins-official/tree/main/plugins/example-plugin).

## Safety model

File infobases are copied to a disposable `onec-dev-*` session by default. Every command writes logs, `/DumpResult`, backups, and artifacts under that marked session. Cleanup validates the marker, directory name, and absence of symbolic links before deleting only that session.

Passwords are read from an environment variable and never stored in the manifest. Existing extensions are backed up in editable and database forms before replacement. The CLI has no command for erasing infobase data or deleting all extensions.

Read [the safety contract](skills/onec-dev/references/safety-contract.md) before using a live infobase.

## Requirements

- Python 3.10 or newer; no third-party Python packages.
- A locally installed 1C:Enterprise platform with Designer batch mode.
- Access to the target infobase.

An agent running in the cloud still needs a runner on the machine that can access 1C and the infobase. The skill format is portable; the 1C runtime is not bundled.

## Install

Clone or download the repository. Do not run unreviewed forks against a production infobase.

### Codex

```powershell
py install.py --agent codex
```

On Linux or macOS, use `python3 install.py --agent codex`. Restart Codex after installation, then invoke `$onec-dev`.

The project also contains `.codex-plugin/plugin.json` for plugin packaging and local development.

### Claude Code

Run directly from a checkout:

```bash
claude --plugin-dir /absolute/path/to/onec-dev-toolkit
```

Or install the individual skills and shared CLI:

```bash
python3 install.py --agent claude
```

### Other agents

Install into any Agent Skills directory:

```bash
python3 install.py --target /path/to/agent/skills
```

The installer copies the shared CLI to the per-user application-data directory documented in the safety contract. It refuses to overwrite an existing skill unless `--upgrade` is supplied.

## First safe run

Discover the platform:

```powershell
py scripts/onec.py discover
```

Create a sandbox session for a file infobase:

```powershell
py scripts/onec.py session-create `
  --base-file "C:\path\to\base" `
  --user "Администратор"
```

Use the returned manifest path:

```powershell
py scripts/onec.py selective-export `
  --session "C:\path\to\onec-dev-...\manifest.json" `
  --object "Catalog.Номенклатура"
```

Always finish:

```powershell
py scripts/onec.py session-cleanup `
  --session "C:\path\to\onec-dev-...\manifest.json"
```

Run `py scripts/onec.py <command> --help` for all command options.

When scaffolding an extension, the CLI selectively exports `Configuration` and its exact default `Language.*`. It creates a mapped adopted language with a distinct extension UUID instead of assuming every configuration is Russian or reusing a conflicting internal identifier.

## Validate the project

```bash
python3 -m unittest discover -s tests -v
```

The CI suite checks Python behavior, manifests, Agent Skill frontmatter, and cleanup guards. Local 1C integration tests are documented in [tests/INTEGRATION.md](tests/INTEGRATION.md); the completed UNF run is recorded in [tests/INTEGRATION-2026-08-11.md](tests/INTEGRATION-2026-08-11.md). CI runners do not include a licensed 1C platform or infobase.

## Scope and status

Version `0.1.0` targets Designer command-line workflows tested with 1C:Enterprise `8.5.1.1343`. Selective dump behavior depends on a platform version that supports `-listFile`. Test on a disposable copy before adopting another platform or configuration version.

1C and 1C:Enterprise are trademarks of their respective owner. This community project is not affiliated with or endorsed by 1C Company.

## License

[MIT](LICENSE)
