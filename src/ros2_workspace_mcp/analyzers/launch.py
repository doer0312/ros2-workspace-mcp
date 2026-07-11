"""Sandboxed single-file ROS 2 launch analysis."""

from pathlib import Path

from ros2_workspace_mcp.config import ServerSettings
from ros2_workspace_mcp.models.common import ScanIssue, Severity
from ros2_workspace_mcp.models.launch import LaunchAnalysisResult
from ros2_workspace_mcp.parsers.launch import (
    parse_python_launch,
    parse_xml_launch,
    parse_yaml_launch,
)
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

LAUNCH_MAX_BYTES = 1024 * 1024
_FORMATS = {
    ".launch.py": ("python", parse_python_launch),
    ".launch.xml": ("xml", parse_xml_launch),
    ".launch.yaml": ("yaml", parse_yaml_launch),
    ".launch.yml": ("yaml", parse_yaml_launch),
}


def _error(code: str, message: str, relative_path: str | None) -> LaunchAnalysisResult:
    return LaunchAnalysisResult(
        relative_path=relative_path,
        format=None,
        valid=False,
        issues=[
            ScanIssue(
                severity=Severity.ERROR,
                code=code,
                message=message,
                path=relative_path or ".",
            )
        ],
    )


def analyze_launch_file(settings: ServerSettings, *, relative_path: str) -> LaunchAnalysisResult:
    """Analyze one launch file without importing or executing it."""
    raw_path = Path(relative_path)
    if raw_path.is_absolute():
        return _error(
            "ABSOLUTE_PATH_NOT_ALLOWED",
            "relative_path must be relative to the configured workspace.",
            None,
        )
    matched = next(
        (item for suffix, item in _FORMATS.items() if relative_path.endswith(suffix)), None
    )
    if matched is None:
        return _error(
            "UNSUPPORTED_LAUNCH_FORMAT",
            "Launch file must end with .launch.py, .launch.xml, .launch.yaml, or .launch.yml.",
            relative_path,
        )
    format_name, parser = matched
    try:
        path = resolve_within_root(settings.root_path, raw_path, require_directory=False)
        text = read_text_file_with_limit(
            settings.root_path,
            path,
            max_bytes=LAUNCH_MAX_BYTES,
        )
    except PathOutsideRootError:
        return _error(
            "PATH_OUTSIDE_ROOT",
            "Launch path resolves outside the configured workspace.",
            relative_path,
        )
    except TextFileTooLargeError:
        return _error(
            "LAUNCH_FILE_TOO_LARGE",
            "Launch file exceeds the configured size limit.",
            relative_path,
        )
    except (InvalidWorkspacePathError, SafeTextReadError):
        return _error(
            "LAUNCH_FILE_READ_ERROR",
            "Launch file does not exist or is not readable UTF-8 text.",
            relative_path,
        )

    result = parser(text, path.relative_to(settings.root_path).as_posix())
    result.format = format_name
    for include in result.includes:
        if include.dynamic or not include.path:
            continue
        include_path = Path(include.path)
        candidate = include_path if include_path.is_absolute() else path.parent / include_path
        try:
            resolve_within_root(settings.root_path, candidate, require_directory=False)
            include.resolvable = True
        except (InvalidWorkspacePathError, PathOutsideRootError):
            result.issues.append(
                ScanIssue(
                    severity=Severity.WARNING,
                    code="UNRESOLVABLE_LAUNCH_INCLUDE",
                    message="Static include path is missing or outside the workspace.",
                    path=result.relative_path or relative_path,
                    context={"include": include.path},
                )
            )
    result.valid = not any(issue.severity is Severity.ERROR for issue in result.issues)
    return result
