# Extension transaction model

## New extension

1. Confirm the name is absent with `extension-list`.
2. Scaffold or load it.
3. Validate syntax and applicability.
4. Update only that extension's database configuration.
5. Dump the database form to `.cfe` as a verification artifact.
6. Delete the extension if the task is abandoned; cleanup removes the sandbox afterward.

## Pre-existing extension

1. Confirm the exact name.
2. Preserve both states before replacement:
   - `/DumpCfg ... -Extension <name>` for editable configuration.
   - `/DumpDBCfg ... -Extension <name>` for database configuration.
3. Load the replacement.
4. If validation fails before database update, use `/RollbackCfg -Extension <name>` or reload the editable backup as appropriate.
5. If a database update was performed and must be undone, reload the saved `.cfe`, validate it, and update that exact extension again.
6. Do not delete a pre-existing extension as a rollback mechanism.

The wrapper performs step 2 automatically when `extension-load-files` or `extension-load-cfe` sees an extension that predates the session. It also backs up a session-created extension after its first successful database update. Before that first update there is no database form to dump, so retain the session source or input `.cfe`; the wrapper records why backup was skipped.

## Identity and ownership

Use a valid 1C identifier for the extension name, object-name prefix, and module name. Record extensions created by the current session in `manifest.json`. Deletion is allowed by default only for those recorded names and requires exact repeated confirmation.
