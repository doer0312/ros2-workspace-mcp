"""Package-scoped ROS interface inspection and type classification."""

import re
from pathlib import Path

from ros2_workspace_mcp.analyzers.package import inspect_package
from ros2_workspace_mcp.analyzers.package_selector import (
    PackageSelectionError,
    resolve_package_selector,
)
from ros2_workspace_mcp.analyzers.workspace import analyze_workspace
from ros2_workspace_mcp.config import ServerSettings
from ros2_workspace_mcp.models.common import ScanIssue, Severity
from ros2_workspace_mcp.models.interface import (
    InterfaceDefinition,
    InterfaceInspectionResult,
    InterfaceTypeScope,
)
from ros2_workspace_mcp.parsers.interfaces import parse_interface_file
from ros2_workspace_mcp.parsers.package_details import parse_package_manifest_details
from ros2_workspace_mcp.parsers.package_xml import PackageXmlError

_INTERFACE_SELECTOR = re.compile(r"^[A-Za-z][A-Za-z0-9_]*(?:\.(?:msg|srv|action))?$")
_BUILTIN_TYPES = frozenset(
    {
        "bool",
        "byte",
        "char",
        "float32",
        "float64",
        "int8",
        "uint8",
        "int16",
        "uint16",
        "int32",
        "uint32",
        "int64",
        "uint64",
        "string",
        "wstring",
        "time",
        "duration",
    }
)


def _error(code: str, message: str) -> InterfaceInspectionResult:
    return InterfaceInspectionResult(
        package_name=None,
        relative_path=None,
        valid=False,
        issues=[
            ScanIssue(
                severity=Severity.ERROR,
                code=code,
                message=message,
                path=".",
            )
        ],
    )


def _workspace_interface_index(settings: ServerSettings) -> dict[str, set[str]]:
    index: dict[str, set[str]] = {}
    for package in analyze_workspace(settings).packages:
        if not package.valid or not package.name:
            continue
        inspection = inspect_package(settings, relative_path=package.relative_path)
        index[package.name] = {Path(path).stem for path in inspection.interface_files}
    return index


def _classify_types(
    definition: InterfaceDefinition,
    *,
    current_package: str,
    index: dict[str, set[str]],
) -> None:
    unresolved: set[str] = set()
    for section in definition.sections:
        for field in section.fields:
            if field.base_type in _BUILTIN_TYPES or (
                field.package_name == "builtin_interfaces"
                and field.base_type in {"Time", "Duration"}
            ):
                field.type_scope = InterfaceTypeScope.BUILTIN
            elif field.package_name is None:
                if field.base_type in index.get(current_package, set()):
                    field.type_scope = InterfaceTypeScope.WORKSPACE
                else:
                    field.type_scope = InterfaceTypeScope.UNRESOLVED_LOCAL
                    unresolved.add(field.base_type)
            elif field.package_name in index:
                if field.base_type in index[field.package_name]:
                    field.type_scope = InterfaceTypeScope.WORKSPACE
                else:
                    field.type_scope = InterfaceTypeScope.UNRESOLVED_LOCAL
                    unresolved.add(f"{field.package_name}/{field.base_type}")
            else:
                field.type_scope = InterfaceTypeScope.EXTERNAL
    definition.unresolved_types = sorted(unresolved)
    for unresolved_type in definition.unresolved_types:
        definition.issues.append(
            ScanIssue(
                severity=Severity.WARNING,
                code="UNRESOLVED_LOCAL_TYPE",
                message="A local or workspace interface type could not be resolved.",
                path=definition.relative_path,
                package_name=current_package,
                context={"type": unresolved_type},
            )
        )
    definition.valid = not any(issue.severity is Severity.ERROR for issue in definition.issues)


def inspect_interfaces(
    settings: ServerSettings,
    *,
    package_name: str | None = None,
    relative_path: str | None = None,
    interface_name: str | None = None,
) -> InterfaceInspectionResult:
    """Inspect selected package interfaces without ROS type generation."""
    if interface_name is not None and not _INTERFACE_SELECTOR.fullmatch(interface_name):
        return _error(
            "INVALID_INTERFACE_NAME",
            "interface_name must be a simple name with an optional msg/srv/action suffix.",
        )
    try:
        package_dir, selected_relative = resolve_package_selector(
            settings,
            package_name=package_name,
            relative_path=relative_path,
        )
        manifest = parse_package_manifest_details(settings.root_path, package_dir / "package.xml")
    except PackageSelectionError as exc:
        return _error(exc.code, str(exc))
    except PackageXmlError as exc:
        return _error("INVALID_PACKAGE_XML", str(exc))
    if not manifest.name:
        return _error("MISSING_PACKAGE_NAME", "Selected package has no manifest name.")

    package_inspection = inspect_package(settings, relative_path=selected_relative)
    paths = package_inspection.interface_files
    if interface_name:
        requested_stem, separator, requested_kind = interface_name.partition(".")
        paths = [
            path
            for path in paths
            if Path(path).stem == requested_stem
            and (not separator or Path(path).suffix == f".{requested_kind}")
        ]
    if interface_name and not paths:
        return InterfaceInspectionResult(
            package_name=manifest.name,
            relative_path=selected_relative,
            interface_name=interface_name,
            valid=False,
            issues=[
                ScanIssue(
                    severity=Severity.ERROR,
                    code="INTERFACE_NOT_FOUND",
                    message="The requested interface was not found in the selected package.",
                    path=selected_relative,
                    package_name=manifest.name,
                )
            ],
        )

    index = _workspace_interface_index(settings)
    definitions = []
    for relative in paths:
        path = settings.root_path / relative
        kind = path.suffix[1:]
        definition = parse_interface_file(settings.root_path, path, kind=kind)
        _classify_types(definition, current_package=manifest.name, index=index)
        definitions.append(definition)
    definitions.sort(key=lambda item: (item.name, item.kind, item.relative_path))
    issues = [issue for definition in definitions for issue in definition.issues]
    return InterfaceInspectionResult(
        package_name=manifest.name,
        relative_path=selected_relative,
        interface_name=interface_name,
        valid=not any(issue.severity is Severity.ERROR for issue in issues),
        interfaces=definitions,
        issues=issues,
    )
