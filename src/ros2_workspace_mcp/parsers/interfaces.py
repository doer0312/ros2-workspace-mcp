"""Bounded parser for ROS .msg, .srv, and .action syntax."""

import re
from pathlib import Path

from ros2_workspace_mcp.models.common import ScanIssue, Severity
from ros2_workspace_mcp.models.interface import (
    ArrayKind,
    InterfaceConstant,
    InterfaceDefinition,
    InterfaceField,
    InterfaceSection,
)
from ros2_workspace_mcp.security.files import (
    SafeTextReadError,
    TextFileTooLargeError,
    read_text_file_with_limit,
)

INTERFACE_MAX_BYTES = 512 * 1024
_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
_TYPE = re.compile(
    r"^(?P<base>[A-Za-z][A-Za-z0-9_]*(?:/[A-Za-z][A-Za-z0-9_]*)?)"
    r"(?P<string><=\d+)?(?P<array>\[\]|\[\d+\]|\[<=\d+\])?$"
)


def _issue(code: str, message: str, path: str, line: int | None = None) -> ScanIssue:
    return ScanIssue(
        severity=Severity.ERROR,
        code=code,
        message=message,
        path=path,
        line=line,
    )


def _parse_type(raw_type: str) -> tuple[str, str | None, ArrayKind, int | None, int | None]:
    match = _TYPE.fullmatch(raw_type)
    if match is None:
        raise ValueError("invalid interface type")
    qualified = match.group("base")
    package_name, separator, base_type = qualified.partition("/")
    if not separator:
        base_type = package_name
        package_name = None
    string_bound = int(match.group("string")[2:]) if match.group("string") else None
    array = match.group("array")
    if array is None:
        array_kind, array_bound = ArrayKind.NONE, None
    elif array == "[]":
        array_kind, array_bound = ArrayKind.UNBOUNDED, None
    elif array.startswith("[<="):
        array_kind, array_bound = ArrayKind.BOUNDED, int(array[3:-1])
    else:
        array_kind, array_bound = ArrayKind.FIXED, int(array[1:-1])
    return base_type, package_name, array_kind, array_bound, string_bound


def _sections_for_kind(kind: str) -> list[str]:
    return {
        "msg": ["message"],
        "srv": ["request", "response"],
        "action": ["goal", "result", "feedback"],
    }[kind]


def parse_interface_text(text: str, *, kind: str, relative_path: str) -> InterfaceDefinition:
    """Parse interface text into fields, constants, sections, and issues."""
    expected_names = _sections_for_kind(kind)
    section_index = 0
    sections = [InterfaceSection(name=name) for name in expected_names]
    issues: list[ScanIssue] = []
    separator_count = 0
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        content = raw_line.split("#", 1)[0].strip()
        if not content:
            continue
        if content == "---":
            separator_count += 1
            section_index += 1
            if section_index >= len(sections):
                issues.append(
                    _issue(
                        "INVALID_INTERFACE_SEPARATOR",
                        "Too many section separators for this interface kind.",
                        relative_path,
                        line_number,
                    )
                )
                section_index = len(sections) - 1
            continue
        parts = content.split(maxsplit=1)
        if len(parts) != 2:
            issues.append(
                _issue(
                    "INVALID_INTERFACE_FIELD",
                    "Interface line must contain a type and name.",
                    relative_path,
                    line_number,
                )
            )
            continue
        raw_type, declaration = parts
        try:
            base_type, package_name, array_kind, array_bound, string_bound = _parse_type(raw_type)
        except ValueError:
            issues.append(
                _issue(
                    "INVALID_INTERFACE_TYPE",
                    "Interface field type is invalid.",
                    relative_path,
                    line_number,
                )
            )
            continue

        name_value = declaration.split("=", 1)
        name = name_value[0].strip().split(maxsplit=1)[0]
        trailing_default = declaration[len(name) :].strip()
        value = name_value[1].strip() if len(name_value) == 2 else trailing_default or None
        if not _NAME.fullmatch(name):
            issues.append(
                _issue(
                    "INVALID_INTERFACE_FIELD",
                    "Interface field or constant name is invalid.",
                    relative_path,
                    line_number,
                )
            )
            continue
        if len(name_value) == 2 and name.upper() == name:
            sections[section_index].constants.append(
                InterfaceConstant(
                    name=name,
                    raw_type=raw_type,
                    value=value or "",
                    line_number=line_number,
                )
            )
        else:
            sections[section_index].fields.append(
                InterfaceField(
                    name=name,
                    raw_type=raw_type,
                    base_type=base_type,
                    package_name=package_name,
                    array_kind=array_kind,
                    array_bound=array_bound,
                    string_bound=string_bound,
                    default_value=value,
                    line_number=line_number,
                )
            )

    expected_separators = len(expected_names) - 1
    if separator_count != expected_separators:
        issues.append(
            _issue(
                "INVALID_INTERFACE_SEPARATOR",
                f"Expected {expected_separators} section separator(s).",
                relative_path,
            )
        )
    referenced = sorted(
        {
            field.raw_type
            for section in sections
            for field in section.fields
            if field.package_name is not None or field.base_type[:1].isupper()
        }
    )
    return InterfaceDefinition(
        name=Path(relative_path).stem,
        relative_path=relative_path,
        kind=kind,
        valid=not issues,
        sections=sections,
        referenced_types=referenced,
        issues=issues,
    )


def parse_interface_file(root: Path, path: Path, *, kind: str) -> InterfaceDefinition:
    """Safely read and parse one interface file."""
    relative = path.relative_to(root).as_posix()
    try:
        text = read_text_file_with_limit(root, path, max_bytes=INTERFACE_MAX_BYTES)
    except TextFileTooLargeError as exc:
        return InterfaceDefinition(
            name=path.stem,
            relative_path=relative,
            kind=kind,
            valid=False,
            issues=[_issue("INTERFACE_FILE_TOO_LARGE", str(exc), relative)],
        )
    except SafeTextReadError as exc:
        return InterfaceDefinition(
            name=path.stem,
            relative_path=relative,
            kind=kind,
            valid=False,
            issues=[_issue("INTERFACE_FILE_READ_ERROR", str(exc), relative)],
        )
    return parse_interface_text(text, kind=kind, relative_path=relative)
