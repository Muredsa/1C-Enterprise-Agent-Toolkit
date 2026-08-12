# Integration result: 2026-08-11

Environment:

- 1C:Enterprise platform `8.5.1.1343` on Windows.
- A 2.80 GB demonstration UNF file infobase.
- 1C user `Администратор` without a password.
- All operations ran against an automatic sandbox copy.

Verified behavior:

- Platform discovery selected the installed `1cv8.exe`.
- Selective export of `Catalog.Номенклатура` produced 22 files totaling 610,914 bytes.
- Root `Configuration` and its exact default language were selectively read for extension scaffolding.
- The final generated extension used a distinct internal UUID for its adopted language and passed applicability.
- Extension source loading, quick module check, full configuration check, applicability check, nondynamic database update with warnings as errors, database `.cfe` dump, editable/database backup, rollback, and exact-name deletion all returned `ok: true`.
- The verified database `.cfe` was nonempty at 5,579 bytes.
- The final extension list matched the initial empty list.
- Guarded cleanup removed 212 files totaling 2,822,806,795 bytes.
- Source infobase size, modification time, and SHA-256 were unchanged after the run.

The development run recorded 39 Designer events. Three deliberate intermediate scaffold variants failed applicability and were correctly rejected: first for a missing controlled default language, then for an unresolved mapping, and then for an internal identifier conflict. Those failures drove the final language-mapping implementation; none was ignored because of a process exit code.
