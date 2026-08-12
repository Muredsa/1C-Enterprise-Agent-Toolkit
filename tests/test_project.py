from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_SKILLS = {
    "onec-dev",
    "onec-selective-export",
    "onec-extension-lifecycle",
    "onec-extension-validate",
}


def frontmatter(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if not lines or lines[0] != "---":
        raise AssertionError(f"Missing frontmatter: {path}")
    end = lines.index("---", 1)
    result = {}
    for line in lines[1:end]:
        key, value = line.split(":", 1)
        result[key.strip()] = value.strip()
    return result


class ProjectTests(unittest.TestCase):
    def test_plugin_manifests(self) -> None:
        codex = json.loads((ROOT / ".codex-plugin" / "plugin.json").read_text())
        claude = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text())
        self.assertEqual(codex["name"], "onec-dev-toolkit")
        self.assertEqual(claude["name"], "onec-dev-toolkit")
        self.assertEqual(codex["version"], claude["version"])

    def test_skills_have_portable_frontmatter(self) -> None:
        found = set()
        for skill_file in (ROOT / "skills").glob("*/SKILL.md"):
            metadata = frontmatter(skill_file)
            self.assertEqual(set(metadata), {"name", "description"})
            self.assertGreater(len(metadata["description"]), 80)
            found.add(metadata["name"])
        self.assertEqual(found, EXPECTED_SKILLS)

    def test_openai_agent_metadata_mentions_skill(self) -> None:
        for name in EXPECTED_SKILLS:
            path = ROOT / "skills" / name / "agents" / "openai.yaml"
            text = path.read_text(encoding="utf-8")
            self.assertIn(f"${name}", text)
            short = next(
                line.split(":", 1)[1].strip().strip('"')
                for line in text.splitlines()
                if line.strip().startswith("short_description:")
            )
            self.assertGreaterEqual(len(short), 25)
            self.assertLessEqual(len(short), 64)

    def test_installer_copies_all_skills_and_cli(self) -> None:
        spec = importlib.util.spec_from_file_location("installer", ROOT / "install.py")
        assert spec and spec.loader
        installer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(installer)
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            result = installer.install(
                base / "skills",
                base / "share" / "onec.py",
                upgrade=False,
                dry_run=False,
            )
            self.assertTrue(result["ok"])
            self.assertTrue((base / "share" / "onec.py").is_file())
            self.assertEqual(
                {path.name for path in (base / "skills").iterdir()},
                EXPECTED_SKILLS,
            )
            with self.assertRaises(installer.InstallError):
                installer.install(
                    base / "skills",
                    base / "share" / "onec.py",
                    upgrade=False,
                    dry_run=False,
                )


if __name__ == "__main__":
    unittest.main()
