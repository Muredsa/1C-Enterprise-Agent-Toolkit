# Validation matrix

| Gate | Wrapper command | Designer operation | Purpose |
| --- | --- | --- | --- |
| Quick syntax | `extension-check --profile quick` | `/CheckModules` with thin client, server, external connection, and extended-module checks | Catch BSL syntax and context errors quickly |
| Applicability | `extension-can-apply` | `/CheckCanApplyConfigurationExtensions` | Detect missing methods, incompatible borrowed objects, and extension mapping failures |
| Full configuration | `extension-check --profile full` | `/CheckConfig` with integrity, reference, handler, client/server, and extended-module checks | Catch metadata and handler errors before application |
| Apply | `extension-update` | `/UpdateDBCfg -Dynamic- -WarningsAsErrors -Extension <name>` | Apply only the named extension without a dynamic update |
| Verify artifact | `extension-dump-db` | `/DumpDBCfg ... -Extension <name>` | Prove a nonempty database extension can be serialized |

## Profiles

Use `quick` during short edit cycles. Require `quick`, applicability, and `full` before declaring an implementation complete. Run a focused application-level smoke test as an additional gate when runtime behavior, UI behavior, permissions, scheduled code, or dynamic dispatch matters.

## Verdict

Pass only when the wrapper returns `ok: true`. The wrapper records the command with secrets redacted, process code, `/DumpResult`, duration, diagnostics, stdout, stderr, and log paths in the session manifest.

Warnings fail validation. Successful phrases such as `ошибок не обнаружено` and `предупреждений: 0` are not treated as diagnostics.
