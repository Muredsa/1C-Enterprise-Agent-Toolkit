#!/usr/bin/env python3
"""Safe, agent-neutral automation for 1C:Enterprise Designer batch mode."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform as host_platform
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence
from xml.etree import ElementTree
from xml.sax.saxutils import escape


SCHEMA_VERSION = 1
SESSION_PREFIX = "onec-dev-"
MARKER_NAME = ".onec-session"
MANIFEST_NAME = "manifest.json"
IDENTIFIER_RE = re.compile(r"^[A-Za-zА-Яа-яЁё_][A-Za-zА-Яа-яЁё0-9_]*$")
OBJECT_NAME_RE = re.compile(
    r"^[A-Za-zА-Яа-яЁё_][A-Za-zА-Яа-яЁё0-9_]*"
    r"(?:\.[A-Za-zА-Яа-яЁё_][A-Za-zА-Яа-яЁё0-9_]*)+$"
)
SUCCESS_LOG_PATTERNS = (
    re.compile(r"(?:ошибок|предупреждений)\s+не\s+обнаружено", re.IGNORECASE),
    re.compile(r"(?:ошибок|предупреждений)\s*:\s*0\b", re.IGNORECASE),
    re.compile(r"errors?\s+(?:were\s+)?not\s+found", re.IGNORECASE),
    re.compile(r"\b0\s+errors?\b", re.IGNORECASE),
)
ERROR_LOG_PATTERNS = (
    re.compile(r"\bошиб(?:ка|ки|ке|ку|кой|ок|ками|ках)\b", re.IGNORECASE),
    re.compile(r"\bпредупреждени(?:е|я|й|ю|ем|ями|ях)\b", re.IGNORECASE),
    re.compile(r"не\s+найден(?:а|о|ы)?\s+метод", re.IGNORECASE),
    re.compile(r"не\s+может\s+быть\s+примен", re.IGNORECASE),
    re.compile(r"\bневозможно\b", re.IGNORECASE),
    re.compile(r"\b(?:error|fatal|failed|failure|exception)\b", re.IGNORECASE),
)


class OneCError(RuntimeError):
    """A user-facing safe workflow error."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def print_json(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))


def read_text(path: Path) -> str:
    data = path.read_bytes()
    encodings = ["utf-8-sig", "cp1251"]
    if data.startswith((b"\xff\xfe", b"\xfe\xff")) or b"\x00" in data[:256]:
        encodings.insert(0, "utf-16")
    for encoding in encodings:
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temp_path.replace(path)


def safe_version_tuple(value: str) -> tuple[int, ...]:
    parts = re.findall(r"\d+", value)
    return tuple(int(part) for part in parts[:4]) if parts else (0,)


def platform_version_from_path(path: Path) -> str:
    for parent in path.parents:
        if re.fullmatch(r"\d+(?:\.\d+){2,3}", parent.name):
            return parent.name
    return "unknown"


def discover_platforms() -> list[dict[str, str]]:
    candidates: set[Path] = set()
    which = shutil.which("1cv8") or shutil.which("1cv8.exe")
    if which:
        candidates.add(Path(which))

    system = host_platform.system()
    if system == "Windows":
        roots = [
            os.environ.get("ProgramFiles"),
            os.environ.get("ProgramFiles(x86)"),
        ]
        for root_value in roots:
            if not root_value:
                continue
            root = Path(root_value) / "1cv8"
            if root.is_dir():
                candidates.update(root.glob("*/bin/1cv8.exe"))
                common = root / "common" / "1cestart.exe"
                if common.is_file():
                    candidates.add(common)
    else:
        for pattern in (
            "/opt/1cv8/*/1cv8",
            "/opt/1cv8/x86_64/*/1cv8",
            "/usr/local/bin/1cv8",
            "/usr/bin/1cv8",
        ):
            if "*" in pattern:
                candidates.update(Path("/").glob(pattern.lstrip("/")))
            else:
                path = Path(pattern)
                if path.is_file():
                    candidates.add(path)

    found = []
    for candidate in candidates:
        try:
            resolved = candidate.resolve(strict=True)
        except OSError:
            continue
        if resolved.name.lower() == "1cestart.exe":
            continue
        found.append(
            {
                "path": str(resolved),
                "version": platform_version_from_path(resolved),
            }
        )
    found.sort(key=lambda item: safe_version_tuple(item["version"]), reverse=True)
    return found


def choose_platform(explicit: str | None) -> dict[str, str]:
    if explicit:
        path = Path(explicit).expanduser().resolve(strict=True)
        if not path.is_file():
            raise OneCError(f"Platform executable is not a file: {path}")
        return {"path": str(path), "version": platform_version_from_path(path)}
    platforms = discover_platforms()
    if not platforms:
        raise OneCError("1C:Enterprise platform executable was not found")
    return platforms[0]


def validate_identifier(value: str, label: str) -> str:
    if not IDENTIFIER_RE.fullmatch(value):
        raise OneCError(f"Invalid {label}: {value!r}")
    return value


def validate_object_name(value: str) -> str:
    value = value.strip()
    if value == "Configuration":
        return value
    if not OBJECT_NAME_RE.fullmatch(value):
        raise OneCError(f"Invalid full metadata object name: {value!r}")
    return value


def safe_label(value: str) -> str:
    normalized = re.sub(r"[^A-Za-zА-Яа-яЁё0-9_-]+", "-", value.strip()).strip("-")
    if not normalized or normalized in {".", ".."}:
        raise OneCError(f"Invalid output label: {value!r}")
    return normalized[:80]


def path_is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def resolve_manifest(value: str) -> Path:
    path = Path(value).expanduser().resolve(strict=True)
    if path.is_dir():
        path = path / MANIFEST_NAME
    if not path.is_file():
        raise OneCError(f"Session manifest not found: {path}")
    return path


def load_manifest(value: str) -> tuple[Path, dict[str, Any]]:
    manifest_path = resolve_manifest(value)
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    if data.get("schema_version") != SCHEMA_VERSION:
        raise OneCError("Unsupported session manifest schema")
    root = Path(data["root"]).resolve(strict=True)
    if manifest_path.parent != root:
        raise OneCError("Manifest root does not match its directory")
    marker = root / MARKER_NAME
    if not marker.is_file() or marker.read_text(encoding="utf-8").strip() != data["session_id"]:
        raise OneCError("Session marker is missing or invalid")
    return manifest_path, data


def save_manifest(path: Path, manifest: dict[str, Any]) -> None:
    manifest["updated_at"] = utc_now()
    atomic_write_json(path, manifest)


def next_operation_paths(manifest: dict[str, Any], operation: str) -> tuple[Path, Path]:
    logs = Path(manifest["root"]) / "logs"
    logs.mkdir(exist_ok=True)
    sequence = len(manifest.get("events", [])) + 1
    stem = f"{sequence:03d}-{safe_label(operation)}"
    return logs / f"{stem}.log", logs / f"{stem}.result.txt"


def connection_arguments(manifest: dict[str, Any]) -> list[str]:
    base = manifest["base"]
    kind = base["kind"]
    if kind == "file":
        return ["/F", base["active"]]
    if kind == "server":
        return ["/S", base["address"]]
    if kind == "ib-name":
        return ["/IBName", base["name"]]
    if kind == "connection-string":
        return ["/IBConnectionString", base["value"]]
    raise OneCError(f"Unsupported base kind: {kind}")


def authentication_arguments(manifest: dict[str, Any]) -> tuple[list[str], set[int]]:
    auth = manifest.get("auth", {})
    args: list[str] = []
    secret_indexes: set[int] = set()
    user = auth.get("user")
    if user:
        args.extend(["/N", user])
        if not auth.get("allow_os_auth", False):
            args.append("/WA-")
    password_env = auth.get("password_env")
    if password_env:
        password = os.environ.get(password_env)
        if password is None:
            raise OneCError(f"Password environment variable is not set: {password_env}")
        args.extend(["/P", password])
        secret_indexes.add(len(args) - 1)
    return args, secret_indexes


def redact_arguments(arguments: Sequence[str], secret_values: Iterable[str]) -> list[str]:
    secrets = {value for value in secret_values if value}
    return ["***" if value in secrets else value for value in arguments]


def diagnostic_lines(log_text: str) -> list[str]:
    diagnostics: list[str] = []
    for raw_line in log_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if any(pattern.search(line) for pattern in SUCCESS_LOG_PATTERNS):
            continue
        if any(pattern.search(line) for pattern in ERROR_LOG_PATTERNS):
            diagnostics.append(line)
    return diagnostics


def parse_result_code(path: Path) -> int | None:
    if not path.is_file():
        return None
    match = re.search(r"-?\d+", read_text(path))
    return int(match.group(0)) if match else None


def run_designer(
    manifest_path: Path,
    manifest: dict[str, Any],
    operation_name: str,
    operation_arguments: Sequence[str],
    timeout: int = 1800,
) -> dict[str, Any]:
    log_path, result_path = next_operation_paths(manifest, operation_name)
    auth_args, secret_indexes = authentication_arguments(manifest)
    arguments = (
        ["DESIGNER"]
        + connection_arguments(manifest)
        + auth_args
        + ["/DisableStartupMessages", "/DisableStartupDialogs"]
        + list(operation_arguments)
        + ["/Out", str(log_path), "/DumpResult", str(result_path)]
    )
    secrets = {auth_args[index] for index in secret_indexes}
    command = [manifest["platform"]["path"]] + arguments
    started = time.monotonic()
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
            creationflags=creationflags,
        )
        timed_out = False
        process_code = completed.returncode
        stdout = completed.stdout
        stderr = completed.stderr
    except subprocess.TimeoutExpired as error:
        timed_out = True
        process_code = None
        stdout = error.stdout or ""
        stderr = error.stderr or ""

    log_text = read_text(log_path) if log_path.is_file() else ""
    result_code = parse_result_code(result_path)
    diagnostics = diagnostic_lines(log_text)
    success = (
        not timed_out
        and process_code == 0
        and result_code == 0
        and not diagnostics
    )
    event = {
        "operation": operation_name,
        "created_at": utc_now(),
        "duration_seconds": round(time.monotonic() - started, 3),
        "command": redact_arguments(command, secrets),
        "process_code": process_code,
        "result_code": result_code,
        "timed_out": timed_out,
        "success": success,
        "diagnostics": diagnostics,
        "log": str(log_path),
        "result": str(result_path),
        "stdout": stdout.strip(),
        "stderr": stderr.strip(),
    }
    manifest.setdefault("events", []).append(event)
    save_manifest(manifest_path, manifest)
    return event


def require_success(event: dict[str, Any]) -> None:
    if not event["success"]:
        raise OneCError(
            f"1C operation failed: {event['operation']}; "
            f"inspect {event['log']} and {event['result']}"
        )


def create_output_directory(manifest: dict[str, Any], category: str, label: str) -> Path:
    root = Path(manifest["root"])
    output = root / category / safe_label(label)
    if output.exists():
        raise OneCError(f"Output path already exists: {output}")
    output.mkdir(parents=True)
    manifest.setdefault("outputs", []).append(str(output))
    return output


def extension_names_from_log(log_path: Path) -> list[str]:
    if not log_path.is_file():
        return []
    names = []
    for line in read_text(log_path).splitlines():
        value = line.strip()
        if IDENTIFIER_RE.fullmatch(value):
            names.append(value)
    return sorted(set(names))


def list_extensions(
    manifest_path: Path,
    manifest: dict[str, Any],
    operation_name: str = "extension-list",
) -> tuple[list[str], dict[str, Any]]:
    event = run_designer(
        manifest_path,
        manifest,
        operation_name,
        ["/DumpDBCfgList", "-AllExtensions"],
    )
    require_success(event)
    return extension_names_from_log(Path(event["log"])), event


def sha1_file(path: Path) -> str:
    digest = hashlib.sha1()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def configuration_xml(
    name: str,
    synonym: str,
    prefix: str,
    module_name: str,
    configuration_uuid: str,
    object_ids: Sequence[str],
    compatibility_mode: str,
    default_language: str,
) -> str:
    contained = "\n".join(
        f"\t\t\t<xr:ContainedObject>\n"
        f"\t\t\t\t<xr:ClassId>{class_id}</xr:ClassId>\n"
        f"\t\t\t\t<xr:ObjectId>{object_id}</xr:ObjectId>\n"
        f"\t\t\t</xr:ContainedObject>"
        for class_id, object_id in zip(
            (
                "9cd510cd-abfc-11d4-9434-004095e12fc7",
                "9fcd25a0-4822-11d4-9414-008048da11f9",
                "e3687481-0a87-462c-a166-9f34594f9bba",
                "9de14907-ec23-4a07-96f0-85521cb6b53b",
                "51f2d5d8-ea4d-4064-8892-82951750031e",
                "e68182ea-4237-4383-967f-90c1e3370bc7",
                "fb282519-d103-4dd3-bc12-cb271d631dfc",
            ),
            object_ids,
        )
    )
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<MetaDataObject xmlns="http://v8.1c.ru/8.3/MDClasses" xmlns:app="http://v8.1c.ru/8.2/managed-application/core" xmlns:cfg="http://v8.1c.ru/8.1/data/enterprise/current-config" xmlns:cmi="http://v8.1c.ru/8.2/managed-application/cmi" xmlns:ent="http://v8.1c.ru/8.1/data/enterprise" xmlns:lf="http://v8.1c.ru/8.2/managed-application/logform" xmlns:pal="http://v8.1c.ru/8.1/data/ui/colors/palette" xmlns:style="http://v8.1c.ru/8.1/data/ui/style" xmlns:sys="http://v8.1c.ru/8.1/data/ui/fonts/system" xmlns:v8="http://v8.1c.ru/8.1/data/core" xmlns:v8ui="http://v8.1c.ru/8.1/data/ui" xmlns:web="http://v8.1c.ru/8.1/data/ui/colors/web" xmlns:win="http://v8.1c.ru/8.1/data/ui/colors/windows" xmlns:xen="http://v8.1c.ru/8.3/xcf/enums" xmlns:xpr="http://v8.1c.ru/8.3/xcf/predef" xmlns:xr="http://v8.1c.ru/8.3/xcf/readable" xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" version="2.21">
\t<Configuration uuid="{configuration_uuid}">
\t\t<InternalInfo>
{contained}
\t\t</InternalInfo>
\t\t<Properties>
\t\t\t<ObjectBelonging>Adopted</ObjectBelonging>
\t\t\t<Name>{escape(name)}</Name>
\t\t\t<Synonym><v8:item><v8:lang>ru</v8:lang><v8:content>{escape(synonym)}</v8:content></v8:item></Synonym>
\t\t\t<Comment/>
\t\t\t<ConfigurationExtensionPurpose>Customization</ConfigurationExtensionPurpose>
\t\t\t<KeepMappingToExtendedConfigurationObjectsByIDs>true</KeepMappingToExtendedConfigurationObjectsByIDs>
\t\t\t<NamePrefix>{escape(prefix)}</NamePrefix>
\t\t\t<ConfigurationExtensionCompatibilityMode>{escape(compatibility_mode)}</ConfigurationExtensionCompatibilityMode>
\t\t\t<DefaultRunMode>ManagedApplication</DefaultRunMode>
\t\t\t<UsePurposes><v8:Value xsi:type="app:ApplicationUsePurpose">PlatformApplication</v8:Value></UsePurposes>
\t\t\t<ScriptVariant>Russian</ScriptVariant>
\t\t\t<Vendor/>
\t\t\t<Version>0.1.0</Version>
\t\t\t<Caption/>
\t\t\t<ShortCaption/>
\t\t\t<DefaultLanguage>{escape(default_language)}</DefaultLanguage>
\t\t\t<BriefInformation/>
\t\t\t<DetailedInformation/>
\t\t\t<Copyright/>
\t\t\t<VendorInformationAddress/>
\t\t\t<ConfigurationInformationAddress/>
\t\t</Properties>
\t\t<ChildObjects>
\t\t\t<Language>{escape(default_language.removeprefix("Language."))}</Language>
\t\t\t<CommonModule>{escape(module_name)}</CommonModule>
\t\t</ChildObjects>
\t</Configuration>
</MetaDataObject>
'''


def common_module_xml(module_name: str, module_uuid: str) -> str:
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<MetaDataObject xmlns="http://v8.1c.ru/8.3/MDClasses" xmlns:app="http://v8.1c.ru/8.2/managed-application/core" xmlns:cfg="http://v8.1c.ru/8.1/data/enterprise/current-config" xmlns:cmi="http://v8.1c.ru/8.2/managed-application/cmi" xmlns:ent="http://v8.1c.ru/8.1/data/enterprise" xmlns:lf="http://v8.1c.ru/8.2/managed-application/logform" xmlns:pal="http://v8.1c.ru/8.1/data/ui/colors/palette" xmlns:style="http://v8.1c.ru/8.1/data/ui/style" xmlns:sys="http://v8.1c.ru/8.1/data/ui/fonts/system" xmlns:v8="http://v8.1c.ru/8.1/data/core" xmlns:v8ui="http://v8.1c.ru/8.1/data/ui" xmlns:web="http://v8.1c.ru/8.1/data/ui/colors/web" xmlns:win="http://v8.1c.ru/8.1/data/ui/colors/windows" xmlns:xen="http://v8.1c.ru/8.3/xcf/enums" xmlns:xpr="http://v8.1c.ru/8.3/xcf/predef" xmlns:xr="http://v8.1c.ru/8.3/xcf/readable" xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" version="2.21">
\t<CommonModule uuid="{module_uuid}">
\t\t<InternalInfo/>
\t\t<Properties>
\t\t\t<ObjectBelonging>Native</ObjectBelonging>
\t\t\t<Name>{escape(module_name)}</Name>
\t\t\t<Comment/>
\t\t\t<Global>false</Global>
\t\t\t<ClientManagedApplication>false</ClientManagedApplication>
\t\t\t<Server>true</Server>
\t\t\t<ExternalConnection>true</ExternalConnection>
\t\t\t<ClientOrdinaryApplication>false</ClientOrdinaryApplication>
\t\t\t<ServerCall>false</ServerCall>
\t\t</Properties>
\t</CommonModule>
</MetaDataObject>
'''


def dump_info_xml(
    name: str,
    module_name: str,
    configuration_uuid: str,
    module_uuid: str,
    language_name: str,
    language_uuid: str,
    configuration_hash: str,
    module_metadata_hash: str,
    module_hash: str,
    language_hash: str,
) -> str:
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<ConfigDumpInfo xmlns="http://v8.1c.ru/8.3/xcf/dumpinfo" xmlns:xen="http://v8.1c.ru/8.3/xcf/enums" xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" format="Hierarchical" version="2.21">
\t<ConfigVersions>
\t\t<Metadata name="CommonModule.{escape(module_name)}" id="{module_uuid}" configVersion="{module_metadata_hash}"/>
\t\t<Metadata name="CommonModule.{escape(module_name)}.Module" id="{module_uuid}.0" configVersion="{module_hash}"/>
\t\t<Metadata name="Configuration.{escape(name)}" id="{configuration_uuid}" configVersion="{configuration_hash}"/>
\t\t<Metadata name="Language.{escape(language_name)}" id="{language_uuid}" configVersion="{language_hash}"/>
\t</ConfigVersions>
</ConfigDumpInfo>
'''


def metadata_property(path: Path, object_kind: str, property_name: str) -> str:
    root = ElementTree.parse(path).getroot()
    metadata_object = next(
        (child for child in root if child.tag.rsplit("}", 1)[-1] == object_kind),
        None,
    )
    if metadata_object is None:
        raise OneCError(f"Expected {object_kind} in metadata file: {path}")
    properties = next(
        (
            child
            for child in metadata_object
            if child.tag.rsplit("}", 1)[-1] == "Properties"
        ),
        None,
    )
    if properties is None:
        raise OneCError(f"Properties are missing in metadata file: {path}")
    value = next(
        (
            child
            for child in properties
            if child.tag.rsplit("}", 1)[-1] == property_name
        ),
        None,
    )
    if value is None or not (value.text or "").strip():
        raise OneCError(f"{property_name} is empty in metadata file: {path}")
    return (value.text or "").strip()


def adopt_language_source(
    source: Path,
    output: Path,
    default_language: str,
) -> tuple[Path, str, str, str]:
    language_name = default_language.removeprefix("Language.")
    if not language_name or default_language == language_name:
        raise OneCError("Default language must use the form Language.<name>")
    validate_identifier(language_name, "language name")
    root = ElementTree.parse(source).getroot()
    language = next(
        (child for child in root if child.tag.rsplit("}", 1)[-1] == "Language"),
        None,
    )
    if language is None:
        raise OneCError(f"Expected Language in metadata file: {source}")
    extended_language_uuid = language.attrib.get("uuid", "")
    try:
        uuid.UUID(extended_language_uuid)
    except ValueError as error:
        raise OneCError(
            f"Invalid language UUID in {source}: {extended_language_uuid}"
        ) from error
    if metadata_property(source, "Language", "Name") != language_name:
        raise OneCError(f"Language name does not match {default_language}: {source}")
    text = read_text(source)
    language_uuid = str(uuid.uuid4())
    text = text.replace(
        f'uuid="{extended_language_uuid}"',
        f'uuid="{language_uuid}"',
        1,
    )
    if "<ObjectBelonging>" not in text:
        text = text.replace(
            "<Properties>",
            "<Properties>\n\t\t\t<ObjectBelonging>Adopted</ObjectBelonging>",
            1,
        )
    language_dir = output / "Languages"
    language_dir.mkdir(parents=True)
    destination = language_dir / f"{language_name}.xml"
    destination.write_text(text, encoding="utf-8")
    return destination, language_name, language_uuid, extended_language_uuid


def scaffold_extension_source(
    output: Path,
    name: str,
    synonym: str,
    prefix: str,
    module_name: str,
    compatibility_mode: str,
    default_language: str,
    language_source: Path,
) -> dict[str, str]:
    validate_identifier(name, "extension name")
    validate_identifier(prefix, "name prefix")
    validate_identifier(module_name, "module name")
    validate_object_name(default_language)
    configuration_uuid = str(uuid.uuid4())
    module_uuid = str(uuid.uuid4())
    object_ids = [str(uuid.uuid4()) for _ in range(7)]

    module_dir = output / "CommonModules" / module_name / "Ext"
    module_dir.mkdir(parents=True)
    configuration_path = output / "Configuration.xml"
    module_metadata_path = output / "CommonModules" / f"{module_name}.xml"
    module_path = module_dir / "Module.bsl"
    configuration_path.write_text(
        configuration_xml(
            name,
            synonym,
            prefix,
            module_name,
            configuration_uuid,
            object_ids,
            compatibility_mode,
            default_language,
        ),
        encoding="utf-8",
    )
    module_metadata_path.write_text(
        common_module_xml(module_name, module_uuid), encoding="utf-8"
    )
    module_path.write_text(
        'Функция SmokeTest() Экспорт\n\tВозврат "OK";\nКонецФункции\n',
        encoding="utf-8",
    )
    (
        language_path,
        language_name,
        language_uuid,
        extended_language_uuid,
    ) = adopt_language_source(
        language_source,
        output,
        default_language,
    )
    dump_info_path = output / "ConfigDumpInfo.xml"
    dump_info_path.write_text(
        dump_info_xml(
            name,
            module_name,
            configuration_uuid,
            module_uuid,
            language_name,
            language_uuid,
            sha1_file(configuration_path),
            sha1_file(module_metadata_path),
            sha1_file(module_path),
            sha1_file(language_path),
        ),
        encoding="utf-8",
    )
    return {
        "source": str(output),
        "configuration_uuid": configuration_uuid,
        "module_uuid": module_uuid,
        "module": str(module_path),
        "default_language": default_language,
        "language_uuid": language_uuid,
        "extended_language_uuid": extended_language_uuid,
        "language": str(language_path),
    }


def ensure_no_symlinks(root: Path) -> None:
    if root.is_symlink():
        raise OneCError(f"Session root is a symbolic link: {root}")
    for current_root, directory_names, file_names in os.walk(root, followlinks=False):
        current = Path(current_root)
        for name in directory_names + file_names:
            candidate = current / name
            if candidate.is_symlink():
                raise OneCError(f"Symbolic link found in session: {candidate}")


def create_session(args: argparse.Namespace) -> dict[str, Any]:
    platform_info = choose_platform(args.platform)
    parent = Path(args.workspace_parent or tempfile.gettempdir()).expanduser().resolve()
    parent.mkdir(parents=True, exist_ok=True)
    session_id = str(uuid.uuid4())
    root = parent / f"{SESSION_PREFIX}{datetime.now().strftime('%Y%m%d-%H%M%S')}-{session_id[:8]}"
    root.mkdir()
    (root / MARKER_NAME).write_text(session_id + "\n", encoding="utf-8")
    try:
        if args.base_file:
            supplied = Path(args.base_file).expanduser().resolve(strict=True)
            database_file = supplied if supplied.is_file() else supplied / "1Cv8.1CD"
            database_file = database_file.resolve(strict=True)
            if database_file.name.lower() != "1cv8.1cd":
                raise OneCError("File base must point to 1Cv8.1CD or its directory")
            if args.no_sandbox and not args.allow_live_base:
                raise OneCError("--no-sandbox requires --allow-live-base")
            if args.no_sandbox:
                active = database_file.parent
                sandboxed = False
            else:
                active = root / "sandbox-base"
                active.mkdir()
                shutil.copy2(database_file, active / "1Cv8.1CD")
                sandboxed = True
            base = {
                "kind": "file",
                "source": str(database_file.parent),
                "source_file": str(database_file),
                "active": str(active),
                "sandboxed": sandboxed,
            }
        else:
            if not args.allow_live_base:
                raise OneCError("Non-file bases require --allow-live-base")
            if args.server:
                base = {"kind": "server", "address": args.server, "sandboxed": False}
            elif args.ib_name:
                base = {"kind": "ib-name", "name": args.ib_name, "sandboxed": False}
            else:
                base = {
                    "kind": "connection-string",
                    "value": args.connection_string,
                    "sandboxed": False,
                }

        manifest = {
            "schema_version": SCHEMA_VERSION,
            "session_id": session_id,
            "root": str(root),
            "created_at": utc_now(),
            "updated_at": utc_now(),
            "platform": platform_info,
            "base": base,
            "auth": {
                "user": args.user,
                "password_env": args.password_env,
                "allow_os_auth": args.allow_os_auth,
            },
            "events": [],
            "outputs": [],
            "created_extensions": [],
            "deleted_extensions": [],
        }
        manifest_path = root / MANIFEST_NAME
        atomic_write_json(manifest_path, manifest)
        return {"session": str(manifest_path), "manifest": manifest}
    except Exception:
        ensure_no_symlinks(root)
        shutil.rmtree(root)
        raise


def command_discover(args: argparse.Namespace) -> dict[str, Any]:
    platforms = discover_platforms()
    return {"platforms": platforms, "selected": platforms[0] if platforms else None}


def command_session_status(args: argparse.Namespace) -> dict[str, Any]:
    path, manifest = load_manifest(args.session)
    return {"session": str(path), "manifest": manifest}


def command_selective_export(args: argparse.Namespace) -> dict[str, Any]:
    manifest_path, manifest = load_manifest(args.session)
    objects = [validate_object_name(value) for value in args.object]
    if args.objects_file:
        for line in Path(args.objects_file).expanduser().read_text(encoding="utf-8-sig").splitlines():
            value = line.strip()
            if not value or value.upper().startswith("REM"):
                continue
            objects.append(validate_object_name(value))
    objects = list(dict.fromkeys(objects))
    if not objects:
        raise OneCError("At least one metadata object is required")
    label = args.label or f"objects-{len(manifest.get('events', [])) + 1}"
    output = create_output_directory(manifest, "exports", label)
    list_path = output.parent / f"{output.name}-objects.txt"
    list_path.write_text("\n".join(objects) + "\n", encoding="utf-8")
    manifest.setdefault("outputs", []).append(str(list_path))
    save_manifest(manifest_path, manifest)
    event = run_designer(
        manifest_path,
        manifest,
        "selective-export",
        [
            "/DumpConfigToFiles",
            str(output),
            "-Format",
            "Hierarchical",
            "-listFile",
            str(list_path),
        ],
    )
    require_success(event)
    files = [path for path in output.rglob("*") if path.is_file()]
    return {
        "event": event,
        "objects": objects,
        "output": str(output),
        "file_count": len(files),
        "bytes": sum(path.stat().st_size for path in files),
    }


def command_extension_list(args: argparse.Namespace) -> dict[str, Any]:
    manifest_path, manifest = load_manifest(args.session)
    names, event = list_extensions(manifest_path, manifest)
    return {"event": event, "extensions": names}


def command_extension_scaffold(args: argparse.Namespace) -> dict[str, Any]:
    manifest_path, manifest = load_manifest(args.session)
    name = validate_identifier(args.name, "extension name")
    module_name = validate_identifier(args.module_name, "module name")
    prefix = validate_identifier(args.prefix, "name prefix")
    configuration_export = command_selective_export(
        argparse.Namespace(
            session=args.session,
            object=["Configuration"],
            objects_file=None,
            label=f"scaffold-{name}-configuration",
        )
    )
    configuration_path = Path(configuration_export["output"]) / "Configuration.xml"
    default_language = validate_object_name(
        metadata_property(configuration_path, "Configuration", "DefaultLanguage")
    )
    if not default_language.startswith("Language."):
        raise OneCError(
            f"Unexpected configuration default language: {default_language}"
        )
    language_export = command_selective_export(
        argparse.Namespace(
            session=args.session,
            object=[default_language],
            objects_file=None,
            label=f"scaffold-{name}-language",
        )
    )
    language_name = default_language.removeprefix("Language.")
    language_path = Path(language_export["output"]) / "Languages" / f"{language_name}.xml"
    if not language_path.is_file():
        raise OneCError(f"Default language export is missing: {language_path}")
    manifest_path, manifest = load_manifest(args.session)
    output = create_output_directory(manifest, "extension-sources", name)
    save_manifest(manifest_path, manifest)
    result = scaffold_extension_source(
        output,
        name,
        args.synonym or name,
        prefix,
        module_name,
        args.compatibility_mode,
        default_language,
        language_path,
    )
    result["configuration_export"] = configuration_export
    result["language_export"] = language_export
    return result


def command_extension_dump(args: argparse.Namespace) -> dict[str, Any]:
    manifest_path, manifest = load_manifest(args.session)
    name = validate_identifier(args.name, "extension name")
    output = create_output_directory(manifest, "extension-dumps", args.label or name)
    save_manifest(manifest_path, manifest)
    event = run_designer(
        manifest_path,
        manifest,
        "extension-dump",
        [
            "/DumpConfigToFiles",
            str(output),
            "-Format",
            "Hierarchical",
            "-Extension",
            name,
        ],
    )
    require_success(event)
    return {"event": event, "output": str(output)}


def command_extension_backup(args: argparse.Namespace) -> dict[str, Any]:
    manifest_path, manifest = load_manifest(args.session)
    name = validate_identifier(args.name, "extension name")
    output = create_output_directory(
        manifest,
        "backups",
        f"{name}-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
    )
    save_manifest(manifest_path, manifest)
    editable = output / f"{name}-editable.cfe"
    database = output / f"{name}-database.cfe"
    editable_event = run_designer(
        manifest_path,
        manifest,
        "extension-backup-editable",
        ["/DumpCfg", str(editable), "-Extension", name],
    )
    require_success(editable_event)
    database_event = run_designer(
        manifest_path,
        manifest,
        "extension-backup-database",
        ["/DumpDBCfg", str(database), "-Extension", name],
    )
    require_success(database_event)
    return {
        "editable_event": editable_event,
        "database_event": database_event,
        "editable": str(editable),
        "database": str(database),
    }


def track_extension_creation(
    manifest_path: Path,
    manifest: dict[str, Any],
    name: str,
    preexisting: bool,
) -> None:
    if not preexisting and name not in manifest["created_extensions"]:
        manifest["created_extensions"].append(name)
        save_manifest(manifest_path, manifest)


def extension_was_applied(manifest: dict[str, Any], name: str) -> bool:
    return any(
        event.get("operation") == "extension-update"
        and event.get("success") is True
        and name in event.get("command", [])
        for event in manifest.get("events", [])
    )


def command_extension_load_files(args: argparse.Namespace) -> dict[str, Any]:
    manifest_path, manifest = load_manifest(args.session)
    name = validate_identifier(args.name, "extension name")
    source = Path(args.source).expanduser().resolve(strict=True)
    if not source.is_dir():
        raise OneCError(f"Extension source is not a directory: {source}")
    existing, list_event = list_extensions(
        manifest_path, manifest, "extension-list-before-load"
    )
    backup = None
    backup_skipped = None
    session_created = name in manifest.get("created_extensions", [])
    if name in existing and (not session_created or extension_was_applied(manifest, name)):
        backup = command_extension_backup(
            argparse.Namespace(session=args.session, name=name)
        )
        manifest_path, manifest = load_manifest(args.session)
    elif name in existing:
        backup_skipped = (
            "Session-created extension has no applied database state yet; "
            "retain its source tree and use extension-rollback after the first update"
        )
    event = run_designer(
        manifest_path,
        manifest,
        "extension-load-files",
        ["/LoadConfigFromFiles", str(source), "-Extension", name],
    )
    require_success(event)
    track_extension_creation(manifest_path, manifest, name, name in existing)
    return {
        "list_event": list_event,
        "event": event,
        "name": name,
        "preexisting": name in existing,
        "backup": backup,
        "backup_skipped": backup_skipped,
    }


def command_extension_load_cfe(args: argparse.Namespace) -> dict[str, Any]:
    manifest_path, manifest = load_manifest(args.session)
    name = validate_identifier(args.name, "extension name")
    source = Path(args.source).expanduser().resolve(strict=True)
    if not source.is_file() or source.suffix.lower() != ".cfe":
        raise OneCError(f"Extension file must be a .cfe file: {source}")
    existing, list_event = list_extensions(
        manifest_path, manifest, "extension-list-before-load"
    )
    backup = None
    backup_skipped = None
    session_created = name in manifest.get("created_extensions", [])
    if name in existing and (not session_created or extension_was_applied(manifest, name)):
        backup = command_extension_backup(
            argparse.Namespace(session=args.session, name=name)
        )
        manifest_path, manifest = load_manifest(args.session)
    elif name in existing:
        backup_skipped = (
            "Session-created extension has no applied database state yet; "
            "retain its input .cfe and use extension-rollback after the first update"
        )
    event = run_designer(
        manifest_path,
        manifest,
        "extension-load-cfe",
        ["/LoadCfg", str(source), "-Extension", name],
    )
    require_success(event)
    track_extension_creation(manifest_path, manifest, name, name in existing)
    return {
        "list_event": list_event,
        "event": event,
        "name": name,
        "preexisting": name in existing,
        "backup": backup,
        "backup_skipped": backup_skipped,
    }


def command_extension_check(args: argparse.Namespace) -> dict[str, Any]:
    manifest_path, manifest = load_manifest(args.session)
    name = validate_identifier(args.name, "extension name")
    if args.profile == "quick":
        operation_arguments = [
            "/CheckModules",
            "-ThinClient",
            "-Server",
            "-ExternalConnection",
            "-ExtendedModulesCheck",
            "-Extension",
            name,
        ]
    else:
        operation_arguments = [
            "/CheckConfig",
            "-ConfigLogIntegrity",
            "-IncorrectReferences",
            "-ThinClient",
            "-Server",
            "-ExternalConnection",
            "-HandlersExistence",
            "-ExtendedModulesCheck",
            "-Extension",
            name,
        ]
    event = run_designer(
        manifest_path,
        manifest,
        f"extension-check-{args.profile}",
        operation_arguments,
    )
    require_success(event)
    return {"event": event, "profile": args.profile}


def command_extension_can_apply(args: argparse.Namespace) -> dict[str, Any]:
    manifest_path, manifest = load_manifest(args.session)
    name = validate_identifier(args.name, "extension name")
    event = run_designer(
        manifest_path,
        manifest,
        "extension-can-apply",
        ["/CheckCanApplyConfigurationExtensions", "-Extension", name],
    )
    require_success(event)
    return {"event": event}


def command_extension_update(args: argparse.Namespace) -> dict[str, Any]:
    manifest_path, manifest = load_manifest(args.session)
    name = validate_identifier(args.name, "extension name")
    event = run_designer(
        manifest_path,
        manifest,
        "extension-update",
        [
            "/UpdateDBCfg",
            "-Dynamic-",
            "-WarningsAsErrors",
            "-Extension",
            name,
        ],
    )
    require_success(event)
    return {"event": event}


def command_extension_dump_db(args: argparse.Namespace) -> dict[str, Any]:
    manifest_path, manifest = load_manifest(args.session)
    name = validate_identifier(args.name, "extension name")
    output = create_output_directory(
        manifest,
        "database-dumps",
        f"{name}-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
    )
    save_manifest(manifest_path, manifest)
    cfe = output / f"{name}.cfe"
    event = run_designer(
        manifest_path,
        manifest,
        "extension-dump-database",
        ["/DumpDBCfg", str(cfe), "-Extension", name],
    )
    require_success(event)
    return {"event": event, "cfe": str(cfe), "bytes": cfe.stat().st_size}


def command_extension_rollback(args: argparse.Namespace) -> dict[str, Any]:
    manifest_path, manifest = load_manifest(args.session)
    name = validate_identifier(args.name, "extension name")
    event = run_designer(
        manifest_path,
        manifest,
        "extension-rollback",
        ["/RollbackCfg", "-Extension", name],
    )
    require_success(event)
    return {"event": event}


def command_extension_delete(args: argparse.Namespace) -> dict[str, Any]:
    manifest_path, manifest = load_manifest(args.session)
    name = validate_identifier(args.name, "extension name")
    if args.confirm_name != name:
        raise OneCError("--confirm-name must exactly match --name")
    created = name in manifest.get("created_extensions", [])
    if not created and not args.allow_existing:
        raise OneCError(
            "Refusing to delete a pre-existing extension; use --allow-existing explicitly"
        )
    event = run_designer(
        manifest_path,
        manifest,
        "extension-delete",
        ["/DeleteCfg", "-Extension", name],
    )
    require_success(event)
    if name not in manifest["deleted_extensions"]:
        manifest["deleted_extensions"].append(name)
    save_manifest(manifest_path, manifest)
    return {"event": event, "deleted": name}


def command_session_cleanup(args: argparse.Namespace) -> dict[str, Any]:
    manifest_path, manifest = load_manifest(args.session)
    root = Path(manifest["root"]).resolve(strict=True)
    parent = root.parent.resolve(strict=True)
    home = Path.home().resolve()
    cwd = Path.cwd().resolve()
    if root in {Path(root.anchor), parent, home, cwd} or path_is_relative_to(cwd, root):
        raise OneCError(f"Refusing unsafe cleanup target: {root}")
    if not root.name.startswith(SESSION_PREFIX):
        raise OneCError(f"Unexpected session directory name: {root.name}")
    if not path_is_relative_to(manifest_path, root):
        raise OneCError("Manifest is outside the session root")
    ensure_no_symlinks(root)
    file_count = 0
    total_bytes = 0
    for path in root.rglob("*"):
        if path.is_file():
            file_count += 1
            total_bytes += path.stat().st_size
    shutil.rmtree(root)
    if root.exists():
        raise OneCError(f"Session cleanup failed: {root}")
    return {
        "removed": str(root),
        "file_count": file_count,
        "bytes": total_bytes,
        "recoverable": False,
    }


def add_session_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--session", required=True, help="Manifest path or session directory")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Safe automation for 1C:Enterprise Designer batch mode"
    )
    parser.add_argument("--version", action="version", version="onec.py 0.1.0")
    subparsers = parser.add_subparsers(dest="command", required=True)

    discover = subparsers.add_parser("discover", help="Discover installed 1C platforms")
    discover.set_defaults(handler=command_discover)

    create = subparsers.add_parser("session-create", help="Create an isolated work session")
    base_group = create.add_mutually_exclusive_group(required=True)
    base_group.add_argument("--base-file")
    base_group.add_argument("--server")
    base_group.add_argument("--ib-name")
    base_group.add_argument("--connection-string")
    create.add_argument("--platform")
    create.add_argument("--user")
    create.add_argument("--password-env")
    create.add_argument("--allow-os-auth", action="store_true")
    create.add_argument("--workspace-parent")
    create.add_argument("--no-sandbox", action="store_true")
    create.add_argument("--allow-live-base", action="store_true")
    create.set_defaults(handler=create_session)

    status = subparsers.add_parser("session-status", help="Show session state")
    add_session_argument(status)
    status.set_defaults(handler=command_session_status)

    export = subparsers.add_parser(
        "selective-export", help="Export only named configuration objects"
    )
    add_session_argument(export)
    export.add_argument("--object", action="append", default=[])
    export.add_argument("--objects-file")
    export.add_argument("--label")
    export.set_defaults(handler=command_selective_export)

    extension_list = subparsers.add_parser("extension-list")
    add_session_argument(extension_list)
    extension_list.set_defaults(handler=command_extension_list)

    scaffold = subparsers.add_parser("extension-scaffold")
    add_session_argument(scaffold)
    scaffold.add_argument("--name", required=True)
    scaffold.add_argument("--synonym")
    scaffold.add_argument("--prefix", default="Ext_")
    scaffold.add_argument("--module-name", default="ExtensionApi")
    scaffold.add_argument("--compatibility-mode", default="Version8_3_14")
    scaffold.set_defaults(handler=command_extension_scaffold)

    extension_dump = subparsers.add_parser("extension-dump")
    add_session_argument(extension_dump)
    extension_dump.add_argument("--name", required=True)
    extension_dump.add_argument("--label")
    extension_dump.set_defaults(handler=command_extension_dump)

    extension_backup = subparsers.add_parser("extension-backup")
    add_session_argument(extension_backup)
    extension_backup.add_argument("--name", required=True)
    extension_backup.set_defaults(handler=command_extension_backup)

    load_files = subparsers.add_parser("extension-load-files")
    add_session_argument(load_files)
    load_files.add_argument("--name", required=True)
    load_files.add_argument("--source", required=True)
    load_files.set_defaults(handler=command_extension_load_files)

    load_cfe = subparsers.add_parser("extension-load-cfe")
    add_session_argument(load_cfe)
    load_cfe.add_argument("--name", required=True)
    load_cfe.add_argument("--source", required=True)
    load_cfe.set_defaults(handler=command_extension_load_cfe)

    check = subparsers.add_parser("extension-check")
    add_session_argument(check)
    check.add_argument("--name", required=True)
    check.add_argument("--profile", choices=("quick", "full"), default="quick")
    check.set_defaults(handler=command_extension_check)

    can_apply = subparsers.add_parser("extension-can-apply")
    add_session_argument(can_apply)
    can_apply.add_argument("--name", required=True)
    can_apply.set_defaults(handler=command_extension_can_apply)

    update = subparsers.add_parser("extension-update")
    add_session_argument(update)
    update.add_argument("--name", required=True)
    update.set_defaults(handler=command_extension_update)

    dump_db = subparsers.add_parser("extension-dump-db")
    add_session_argument(dump_db)
    dump_db.add_argument("--name", required=True)
    dump_db.set_defaults(handler=command_extension_dump_db)

    rollback = subparsers.add_parser("extension-rollback")
    add_session_argument(rollback)
    rollback.add_argument("--name", required=True)
    rollback.set_defaults(handler=command_extension_rollback)

    delete = subparsers.add_parser("extension-delete")
    add_session_argument(delete)
    delete.add_argument("--name", required=True)
    delete.add_argument("--confirm-name", required=True)
    delete.add_argument("--allow-existing", action="store_true")
    delete.set_defaults(handler=command_extension_delete)

    cleanup = subparsers.add_parser("session-cleanup")
    add_session_argument(cleanup)
    cleanup.set_defaults(handler=command_session_cleanup)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result = args.handler(args)
        print_json({"ok": True, **result})
        return 0
    except OneCError as error:
        print_json({"ok": False, "error": str(error)})
        return 1
    except (OSError, json.JSONDecodeError, subprocess.SubprocessError) as error:
        print_json({"ok": False, "error": f"{type(error).__name__}: {error}"})
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
