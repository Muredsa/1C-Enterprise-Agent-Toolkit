# Safety contract

## Session ownership

- Create work only inside a directory named `onec-dev-*` containing both `.onec-session` and `manifest.json`.
- Default to a copied file infobase. The source `1Cv8.1CD` is read only for the copy operation.
- Treat server infobases, infobases selected by name or connection string, and `--no-sandbox` file sessions as live. Use them only after explicit authorization with `--allow-live-base`.
- Keep every dump, source tree, backup, log, and result file inside the session root.
- Clean the session with `onec.py session-cleanup`. Do not manually construct a recursive delete command.
- Cleanup must reject missing markers, an unexpected directory name, symbolic links, the filesystem root, the home directory, and the current working directory.

## Authentication

- Pass the 1C user with `--user`.
- Pass only an environment-variable name with `--password-env`; never pass or store the password itself.
- Use `/WA-` when a 1C user is explicit. Enable OS authentication only when the user requests it.
- Redact secrets from recorded commands.

## Allowed mutation boundary

- Modify only one explicitly named configuration extension.
- Back up a pre-existing extension before loading replacement files or a `.cfe`.
- Use `/UpdateDBCfg -Dynamic- -WarningsAsErrors -Extension <name>` only after checks pass.
- Delete only an exact extension name created by the current session. Deleting a pre-existing extension requires a separate explicit override and exact confirmation.
- Never expose a command that deletes all extensions.

## Denied operations

Do not run `/EraseData`, `/DeleteCfg -AllExtensions`, `/ManageCfgSupport -disableSupport`, or a mutating `/IBCheckAndRepair`. Do not update the main database configuration, remove support, erase infobase data, or change scheduled-job state as a side effect of this workflow.

## CLI lookup

Resolve the CLI in this order:

1. `ONEC_DEV_CLI`, if it points to a file.
2. `<project-root>/scripts/onec.py` when running from a cloned plugin.
3. `onec-dev` on `PATH`.
4. `%LOCALAPPDATA%/onec-dev-toolkit/onec.py` on Windows.
5. `~/.local/share/onec-dev-toolkit/onec.py` on Linux and macOS.

Use Python 3.10 or newer for a `.py` path. The CLI uses only the standard library.
