---
name: onec-selective-export
description: Export and inspect only the 1C:Enterprise configuration metadata objects required for a task using Designer `/DumpConfigToFiles -listFile`. Use when asked to study a configuration, locate BSL logic, inspect a catalog, document, register, form, command, or module, or gather dependencies without dumping the whole configuration.
---

# 1C Selective Export

Minimize the exported surface. Expand it only from concrete evidence found in the first dump.

## Export workflow

1. Read [references/object-selection.md](references/object-selection.md).
2. Reuse the isolated session created by `$onec-dev`, or create one under the same safety contract.
3. Normalize each requested object to a full metadata name such as `Catalog.Номенклатура` or `Document.ЗаказПокупателя.Form.ФормаДокумента`.
4. Run `selective-export --session <manifest> --object <full-name>` once per root object. Use repeated `--object` arguments or an UTF-8 `--objects-file` for a small batch.
5. Inspect the exported root XML and BSL. Add a child form, command, template, or referenced common module only when the inspected files show that it is needed.
6. Run a second selective export with only those additional names. Do not switch to a full configuration dump for convenience.
7. Cite the exact exported files used for conclusions.

Example:

```text
onec.py selective-export --session <manifest> \
  --object Catalog.Номенклатура \
  --object Catalog.Номенклатура.Form.ФормаЭлемента \
  --label nomenclature-task
```

## Accuracy rules

- Treat an object name rejected by the CLI as unresolved; do not guess a spelling repeatedly. Confirm it from a known source or ask for the exact object.
- Do not infer all runtime dependencies from text search. Dynamic calls and metadata references can require a targeted runtime check.
- Keep the object list and the generated export in the session manifest so the inspection is auditable.
- Require `ok: true`. Inspect the reported log if a process exits with code zero but the result or diagnostics fail.
- Return control to `$onec-dev` for cleanup after the task.
