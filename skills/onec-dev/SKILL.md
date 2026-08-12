---
name: onec-dev
description: Route safe 1C:Enterprise development work involving an infobase, configuration metadata, selective object export, configuration extensions, Designer batch mode, BSL changes, or extension testing. Use this as the entry point when a request spans several 1C workflows or does not clearly match one focused 1C skill.
---

# 1C Development Router

Operate through an isolated, auditable session. Preserve the source infobase and remove session-owned data after the task.

## Start safely

1. Read [references/safety-contract.md](references/safety-contract.md).
2. Locate `scripts/onec.py`. Check `ONEC_DEV_CLI`, a project checkout two levels above this skill, the executable `onec-dev` on `PATH`, then the user data locations documented in the safety contract.
3. Run `discover` and select the newest compatible platform unless the user requested a specific version.
4. Run `session-create`. For a file infobase, keep the default sandbox copy. Treat server, named, connection-string, and `--no-sandbox` sessions as live and require the user's explicit authorization.
5. Keep the returned manifest path. Pass it to every subsequent command with `--session`.

Never put a password in a command, manifest, log, or chat. Pass only the name of an environment variable with `--password-env`. When an explicit 1C user is supplied, keep OS authentication disabled unless the user explicitly requests it.

## Route the work

- Invoke `$onec-selective-export` to inspect or export only the metadata required for the task.
- Invoke `$onec-extension-lifecycle` to create, load, dump, edit, back up, roll back, or delete one named extension.
- Invoke `$onec-extension-validate` to check BSL, validate applicability, update the extension database configuration, or verify the resulting `.cfe`.
- Combine the focused skills in that order for implementation work: inspect dependencies, modify an extension, then validate it.

Do not change the main configuration for extension work. Do not use destructive Designer switches outside the allowlist in the safety contract.

## Finish deterministically

1. Report the meaningful result and any diagnostics from the JSON output and linked log files.
2. Run `session-cleanup --session <manifest>` in a finally-style step whether the work succeeds or fails.
3. If cleanup fails, stop and report the exact session path. Do not broaden the deletion target or retry with a stronger deletion command.

Do not claim success from the process exit code alone. Require the CLI's `ok: true`; it checks process status, `/DumpResult`, and diagnostic log lines.
