from __future__ import annotations

import argparse
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("onec_cli", ROOT / "scripts" / "onec.py")
assert SPEC and SPEC.loader
onec = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(onec)


class OnecCliTests(unittest.TestCase):
    def test_version_sorting(self) -> None:
        self.assertGreater(
            onec.safe_version_tuple("8.5.1.1343"),
            onec.safe_version_tuple("8.3.27.1000"),
        )

    def test_metadata_and_identifier_validation(self) -> None:
        self.assertEqual(onec.validate_identifier("Тест_1", "name"), "Тест_1")
        self.assertEqual(
            onec.validate_object_name("Catalog.Номенклатура.Form.ФормаЭлемента"),
            "Catalog.Номенклатура.Form.ФормаЭлемента",
        )
        self.assertEqual(onec.validate_object_name("Configuration"), "Configuration")
        with self.assertRaises(onec.OneCError):
            onec.validate_identifier("../bad", "name")
        with self.assertRaises(onec.OneCError):
            onec.validate_object_name("Номенклатура")

    def test_diagnostics_do_not_mistake_success_for_error(self) -> None:
        text = "Синтаксических ошибок не обнаружено!\nПредупреждений: 0"
        self.assertEqual(onec.diagnostic_lines(text), [])

    def test_diagnostics_catch_semantic_failure(self) -> None:
        text = 'Не найден метод "ХостСервисаОбменаДанными"\n'
        self.assertEqual(onec.diagnostic_lines(text), [text.strip()])

    def test_read_text_handles_utf8_and_cp1251(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for encoding in ("utf-8", "cp1251"):
                path = root / f"{encoding}.txt"
                path.write_bytes("Ошибка проверки".encode(encoding))
                self.assertEqual(onec.read_text(path), "Ошибка проверки")

    def test_extension_scaffold_is_complete(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "source"
            output.mkdir()
            language_source = Path(directory) / "Русский.xml"
            language_source.write_text(
                '''<?xml version="1.0" encoding="UTF-8"?>
<MetaDataObject xmlns="http://v8.1c.ru/8.3/MDClasses" version="2.21">
  <Language uuid="af1b61ff-d1b9-4053-ad85-8259b6626adc">
    <Properties>
      <Name>Русский</Name>
      <Synonym/>
      <Comment/>
      <LanguageCode>ru</LanguageCode>
    </Properties>
  </Language>
</MetaDataObject>
''',
                encoding="utf-8",
            )
            result = onec.scaffold_extension_source(
                output,
                "CodexTestExtension",
                "Codex test extension",
                "Cte_",
                "CodexTestApi",
                "Version8_3_14",
                "Language.Русский",
                language_source,
            )
            self.assertTrue((output / "Configuration.xml").is_file())
            self.assertTrue((output / "ConfigDumpInfo.xml").is_file())
            module = Path(result["module"])
            self.assertIn("SmokeTest", module.read_text(encoding="utf-8"))
            self.assertIn(
                "CommonModule.CodexTestApi",
                (output / "ConfigDumpInfo.xml").read_text(encoding="utf-8"),
            )
            language = (output / "Languages" / "Русский.xml").read_text(
                encoding="utf-8"
            )
            self.assertIn("<ObjectBelonging>Adopted</ObjectBelonging>", language)
            self.assertNotIn('uuid="af1b61ff-d1b9-4053-ad85-8259b6626adc"', language)
            self.assertEqual(
                result["extended_language_uuid"],
                "af1b61ff-d1b9-4053-ad85-8259b6626adc",
            )
            self.assertIn(
                "Language.Русский",
                (output / "ConfigDumpInfo.xml").read_text(encoding="utf-8"),
            )

    def test_failed_session_creation_cleans_its_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            args = argparse.Namespace(
                platform=None,
                workspace_parent=directory,
                base_file=str(Path(directory) / "missing"),
                server=None,
                ib_name=None,
                connection_string=None,
                no_sandbox=False,
                allow_live_base=False,
                user="Администратор",
                password_env=None,
                allow_os_auth=False,
            )
            with mock.patch.object(
                onec,
                "choose_platform",
                return_value={"path": "1cv8", "version": "test"},
            ):
                with self.assertRaises(FileNotFoundError):
                    onec.create_session(args)
            self.assertEqual(list(Path(directory).glob("onec-dev-*")), [])

    def test_cleanup_removes_only_marked_session(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            root = parent / "onec-dev-20260811-test"
            root.mkdir()
            session_id = "session-test"
            (root / onec.MARKER_NAME).write_text(session_id + "\n", encoding="utf-8")
            manifest = {
                "schema_version": onec.SCHEMA_VERSION,
                "session_id": session_id,
                "root": str(root.resolve()),
                "events": [],
            }
            manifest_path = root / onec.MANIFEST_NAME
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            (root / "artifact.txt").write_text("temporary", encoding="utf-8")
            result = onec.command_session_cleanup(
                argparse.Namespace(session=str(manifest_path))
            )
            self.assertFalse(root.exists())
            self.assertEqual(result["removed"], str(root.resolve()))

    def test_all_expected_commands_parse(self) -> None:
        parser = onec.build_parser()
        commands = {
            action.dest: set(action.choices or {})
            for action in parser._actions
            if action.dest == "command"
        }
        self.assertIn("selective-export", commands["command"])
        self.assertIn("extension-can-apply", commands["command"])
        self.assertIn("session-cleanup", commands["command"])

    def test_applied_extension_detection_is_exact(self) -> None:
        manifest = {
            "events": [
                {
                    "operation": "extension-update",
                    "success": True,
                    "command": ["1cv8", "-Extension", "ExactName"],
                }
            ]
        }
        self.assertTrue(onec.extension_was_applied(manifest, "ExactName"))
        self.assertFalse(onec.extension_was_applied(manifest, "OtherName"))


if __name__ == "__main__":
    unittest.main()
