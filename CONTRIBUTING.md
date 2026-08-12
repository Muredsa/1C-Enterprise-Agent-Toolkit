# Contributing

Keep each skill narrow, deterministic, and safe for an unattended agent.

1. Open an issue describing the 1C platform version and exact Designer behavior.
2. Add or update a unit test for wrapper logic.
3. Test integration only on a disposable file-infobase copy.
4. Never add credentials, customer configurations, infobases, `.cf`, or `.cfe` artifacts to the repository.
5. Preserve the two-field `name` and `description` frontmatter in every `SKILL.md`.
6. Run `python3 -m unittest discover -s tests -v` before submitting a change.

Changes that add mutating Designer commands must document the rollback path and cleanup boundary. Commands that erase data, remove configuration support, mutate the main configuration during extension work, or delete all extensions are out of scope.
