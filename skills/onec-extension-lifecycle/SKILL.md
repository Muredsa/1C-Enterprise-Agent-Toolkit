---
name: onec-extension-lifecycle
description: Create, dump, edit, load, back up, roll back, and delete one named 1C:Enterprise configuration extension while preserving the main configuration. Use for `.cfe` files, extension source trees, new customization extensions, or changes to an existing extension.
---

# 1C Extension Lifecycle

Keep all customization in one explicitly named extension and use an isolated session by default.

## Choose the path

- For a new extension, run `extension-scaffold`. It selectively reads `Configuration` and its exact default `Language.*`, creates a mapped adopted language with a distinct extension UUID, and creates a hierarchical source tree with one native server common module and a smoke-test function.
- For an existing extension in the infobase, run `extension-dump` to get editable hierarchical sources before changing code.
- For an existing `.cfe`, run `extension-load-cfe` only after identifying the exact target extension name.

Read [references/transaction-model.md](references/transaction-model.md) before loading or deleting anything.

## Implement a change

1. Run `extension-list` and record whether the exact extension name already exists.
2. Create or dump the source tree inside the session. Let the scaffold command derive the controlled `DefaultLanguage`; never hardcode it from a different configuration.
3. Inspect only the required main-configuration objects with `$onec-selective-export`.
4. Edit extension XML and BSL. Keep the extension name and prefix stable. Do not edit the main configuration dump.
5. Run `extension-load-files --name <name> --source <directory>`. The CLI automatically backs up both editable and database forms before replacing a pre-existing extension.
6. Delegate checks and database update to `$onec-extension-validate`.

## Recover

- Before database update, run `extension-rollback` to restore the extension configuration from its database configuration.
- For a new session-created extension, run `extension-delete --name <name> --confirm-name <name>` when abandoning the change.
- For a pre-existing extension, restore the automatic backup rather than deleting it. Never use `--allow-existing` without a separate explicit request to delete that exact extension.
- Finish with the router's `session-cleanup`; this removes sources, dumps, backups, logs, and the sandbox infobase owned by the session.

Require `ok: true` after every command. Stop at the first failed operation and preserve its log path until the failure is reported.
