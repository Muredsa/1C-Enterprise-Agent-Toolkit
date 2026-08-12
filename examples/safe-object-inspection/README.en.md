# Safely inspect an object from any 1C configuration

[Русский](README.md) · **English**

This universal example creates a disposable copy of a file infobase, selectively exports one explicitly named metadata object, and always removes the working session in a `finally` block.

```powershell
.\examples\safe-object-inspection\workflow.ps1 `
  -BaseFile "C:\Bases\MyConfiguration" `
  -Object "Catalog.Products" `
  -User "Administrator"
```

The script has no prior knowledge of the configuration structure: the full metadata name is supplied through `-Object`. It can belong to a standard, industry-specific, or completely custom configuration, for example `Document.CustomerOrder` or `InformationRegister.MyRegister`.

The script prints the export JSON and a short file listing before cleanup. The source `1Cv8.1CD` remains unchanged.

> [!CAUTION]
> Do not add `--no-sandbox` or `--allow-live-base`: this example intentionally operates only on an isolated copy of a file infobase.

UNF was one of the project's integration-test environments, not a requirement or limitation of this workflow.
