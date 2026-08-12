# Local 1C integration test

Use only a disposable copy. The wrapper creates one automatically for a file infobase.

1. `onec.py discover` finds the intended platform.
2. `session-create --base-file <path> --user <user>` records `sandboxed: true`.
3. `selective-export --object Catalog.<known-name>` produces only the requested metadata tree.
4. `extension-list` records the initial extension set.
5. Run `extension-scaffold`; confirm it derives the configuration's default language and gives the adopted language a distinct extension UUID. Then run `extension-load-files`, quick check, applicability check, full check, update, and database dump; all must return `ok: true`.
6. Delete the session-created extension by exact name and confirm the initial extension set is restored.
7. Run `session-cleanup` and confirm the reported directory no longer exists.
8. Confirm the source `1Cv8.1CD` size, modification timestamp, and hash are unchanged.

Review every event in `manifest.json` before cleanup when diagnosing a failure. A zero process code is insufficient if `/DumpResult` or log diagnostics fail.
