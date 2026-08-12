# Object selection

## Canonical names

Use the Designer metadata path accepted by `-listFile`:

- Root object: `Catalog.Номенклатура`, `Document.ЗаказПокупателя`, `InformationRegister.ЦеныНоменклатуры`.
- Child form: `Catalog.Номенклатура.Form.ФормаЭлемента`.
- Child command or template: append `.Command.<name>` or `.Template.<name>` when the root XML proves the child exists.
- Common module: `CommonModule.<name>`.

Names are configuration metadata names, not synonyms shown to users.

## Minimal closure procedure

1. Export the root metadata object.
2. Read its metadata XML to identify owned forms, commands, and templates.
3. Read only the BSL modules relevant to the requested behavior.
4. Search those files for concrete references to other metadata and common modules.
5. Export only the referenced objects needed to answer or implement the task.
6. Repeat until each conclusion or edit has enough source context.

Do not automatically include every owned child. For example, an object-manager change usually does not need every form; a form event change needs the exact form but may not need unrelated templates.

## List file

Write one full metadata name per UTF-8 line. Empty lines are ignored by the wrapper. Lines beginning with `REM` are treated as comments. Keep batches small enough that each exported object has a clear reason.

## Limits

Static inspection cannot reliably discover dynamic `Вычислить`, string-based metadata lookup, reflection, or behavior selected by functional options. State this limit and use a focused application or integration test when it matters.
