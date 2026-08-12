# Contributing

[Русский](CONTRIBUTING.md) · **English**

Keep every skill narrow, deterministic, and safe for an unattended agent.

1. Open an Issue with the 1C platform version and exact Designer behavior.
2. Add or update a unit test for wrapper logic.
3. Run integration checks only on a disposable file-infobase copy.
4. Never add passwords, customer configurations, infobases, `.cf`, `.cfe`, or `1Cv8.1CD` files.
5. Preserve the two-field `name` and `description` frontmatter in every `SKILL.md`.
6. Update Russian and English documentation together.
7. Run `python3 -m unittest discover -s tests -v` before submitting a change.

Mutating commands must document backup, rollback, and cleanup boundaries. Erasing infobase data, removing configuration support, modifying the main configuration during extension work, and deleting every extension are out of scope.
