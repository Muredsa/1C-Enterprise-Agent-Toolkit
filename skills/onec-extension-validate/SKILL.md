---
name: onec-extension-validate
description: Validate a named 1C:Enterprise configuration extension through BSL module checks, full configuration checks, applicability checks, database update, and database `.cfe` verification. Use after creating or modifying an extension, when diagnosing why an extension cannot be applied, or before declaring extension work complete.
---

# 1C Extension Validation

Validate in increasing order of cost and mutation. Stop at the first failed gate.

Read [references/check-matrix.md](references/check-matrix.md), then run these gates against the isolated session:

1. `extension-check --profile quick --name <name>`.
2. `extension-can-apply --name <name>`.
3. `extension-check --profile full --name <name>` for implementation completion or release work.
4. `extension-update --name <name>` only after the prior gates pass. This updates only the named extension with dynamic update disabled and warnings treated as errors.
5. `extension-dump-db --name <name>` and verify the reported `.cfe` exists and has nonzero size.

Do not use the 1C process exit code as the verdict. Require all three signals collected by the wrapper: process code zero, `/DumpResult` zero, and no error or warning diagnostics in `/Out`. A line such as `Не найден метод` is a failure even when the process exits with zero.

## Failure handling

- Preserve and report the exact log and result paths.
- Do not continue to database update after a syntax, full-check, or applicability failure.
- Use `extension-rollback` for an editable extension that has not been applied.
- Use the pre-change backups defined by `$onec-extension-lifecycle` when a pre-existing extension must be restored.
- Run `session-cleanup` after reporting or recovering, including on failure.
