"""Sandboxed URDF and unexpanded Xacro inspection."""

import xml.etree.ElementTree as ET
from pathlib import Path

from ros2_workspace_mcp.config import ServerSettings
from ros2_workspace_mcp.models.common import ScanIssue, Severity
from ros2_workspace_mcp.models.robot import RobotDescriptionInspectionResult
from ros2_workspace_mcp.parsers.robot import parse_robot_description_xml
from ros2_workspace_mcp.security.files import (
    SafeTextReadError,
    TextFileTooLargeError,
    read_text_file_with_limit,
)
from ros2_workspace_mcp.security.paths import (
    InvalidWorkspacePathError,
    PathOutsideRootError,
    resolve_within_root,
)

ROBOT_DESCRIPTION_MAX_BYTES = 1024 * 1024


def _error(code: str, message: str, relative_path: str | None) -> RobotDescriptionInspectionResult:
    return RobotDescriptionInspectionResult(
        relative_path=relative_path,
        format=None,
        valid=False,
        expanded=False,
        issues=[
            ScanIssue(
                severity=Severity.ERROR,
                code=code,
                message=message,
                path=relative_path or ".",
            )
        ],
    )


def _xacro_include_cycles(
    settings: ServerSettings,
    path: Path,
    result: RobotDescriptionInspectionResult,
) -> None:
    if result.xacro_summary is None:
        return
    for include in result.xacro_summary.includes:
        if include.dynamic or not include.resolvable or not include.filename:
            continue
        try:
            included_path = resolve_within_root(
                settings.root_path,
                path.parent / include.filename,
                require_directory=False,
            )
            text = read_text_file_with_limit(
                settings.root_path,
                included_path,
                max_bytes=ROBOT_DESCRIPTION_MAX_BYTES,
            )
            document = ET.fromstring(text)
        except (SafeTextReadError, ET.ParseError, InvalidWorkspacePathError, PathOutsideRootError):
            continue
        for element in document.iter():
            if element.tag.rsplit("}", 1)[-1] != "include":
                continue
            filename = element.get("filename")
            if not filename or "${" in filename or "$(" in filename:
                continue
            try:
                target = resolve_within_root(
                    settings.root_path,
                    included_path.parent / filename,
                    require_directory=False,
                )
            except (InvalidWorkspacePathError, PathOutsideRootError):
                continue
            if target == path:
                cycle = [
                    path.relative_to(settings.root_path).as_posix(),
                    included_path.relative_to(settings.root_path).as_posix(),
                ]
                result.xacro_summary.include_cycles.append(cycle)
                result.issues.append(
                    ScanIssue(
                        severity=Severity.WARNING,
                        code="XACRO_INCLUDE_CYCLE",
                        message="A direct Xacro include cycle was detected.",
                        path=result.relative_path or ".",
                        context={"files": cycle},
                    )
                )


def inspect_robot_description(
    settings: ServerSettings,
    *,
    relative_path: str,
) -> RobotDescriptionInspectionResult:
    """Inspect one URDF or summarize one unexpanded Xacro file."""
    raw_path = Path(relative_path)
    if raw_path.is_absolute():
        return _error(
            "ABSOLUTE_PATH_NOT_ALLOWED",
            "relative_path must be relative to the configured workspace.",
            None,
        )
    format_name = "urdf" if relative_path.endswith(".urdf") else None
    if relative_path.endswith(".xacro"):
        format_name = "xacro"
    if format_name is None:
        return _error(
            "UNSUPPORTED_ROBOT_DESCRIPTION_FORMAT",
            "Robot description must end with .urdf or .xacro.",
            relative_path,
        )
    try:
        path = resolve_within_root(settings.root_path, raw_path, require_directory=False)
        text = read_text_file_with_limit(
            settings.root_path,
            path,
            max_bytes=ROBOT_DESCRIPTION_MAX_BYTES,
        )
    except PathOutsideRootError:
        return _error(
            "PATH_OUTSIDE_ROOT",
            "Robot description resolves outside the workspace.",
            relative_path,
        )
    except TextFileTooLargeError:
        return _error(
            "ROBOT_DESCRIPTION_TOO_LARGE",
            "Robot description exceeds the configured size limit.",
            relative_path,
        )
    except (InvalidWorkspacePathError, SafeTextReadError):
        return _error(
            "ROBOT_DESCRIPTION_READ_ERROR",
            "Robot description is missing or not readable UTF-8 text.",
            relative_path,
        )
    result = parse_robot_description_xml(
        text,
        root=settings.root_path,
        path=path,
        format_name=format_name,
    )
    if format_name == "xacro":
        _xacro_include_cycles(settings, path, result)
    result.valid = not any(issue.severity is Severity.ERROR for issue in result.issues)
    return result
