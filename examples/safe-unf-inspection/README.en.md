# Safely inspect one UNF object

[Русский](README.md) · **English**

This example creates a disposable copy of a file infobase, selectively exports one metadata object, and always removes the working session in a `finally` block.

```powershell
.\examples\safe-unf-inspection\workflow.ps1 `
  -BaseFile "C:\Bases\UNF" `
  -Object "Catalog.Products" `
  -User "Administrator"
```

The script prints the export JSON and a short file listing before cleanup. The source `1Cv8.1CD` remains unchanged.

Pass another full metadata name, such as `Document.CustomerOrder`, to inspect a different object. The same lifecycle works with other configurations.

> [!CAUTION]
> Do not add `--no-sandbox` or `--allow-live-base`: this example intentionally operates only on an isolated copy of a file infobase.
