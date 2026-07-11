"""Compact package-context resource template."""

import json
import re
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ResourceError

from ros2_workspace_mcp.analyzers.package import inspect_package
from ros2_workspace_mcp.analyzers.package_selector import (
    PackageSelectionError,
    resolve_package_selector,
)
from ros2_workspace_mcp.config import ServerSettings
from ros2_workspace_mcp.models.common import ScanIssue, Severity

PACKAGE_NAME_MAX_LENGTH = 64
PACKAGE_RESOURCE_MAX_FILES_PER_KIND = 50
PACKAGE_RESOURCE_MAX_ISSUES = 50
PACKAGE_RESOURCE_MAX_JSON_BYTES = 256 * 1024
_PACKAGE_NAME = re.compile(r"^[a-z][a-z0-9_]*$")


def validate_package_name(package_name: str) -> str:
    """Validate a conservative ROS package name, never a path."""
    if not package_name or len(package_name) > PACKAGE_NAME_MAX_LENGTH:
        raise ResourceError("package_name must contain 1 to 64 characters")
    if not _PACKAGE_NAME.fullmatch(package_name):
        raise ResourceError(
            "package_name may contain only lowercase letters, digits, and underscores"
        )
    return package_name


def _clip(value: str | None, limit: int = 1000) -> tuple[str | None, bool]:
    if value is None or len(value) <= limit:
        return value, False
    return value[:limit], True


def _compact_paths(paths: list[str]) -> tuple[list[str], bool]:
    limited = paths[:PACKAGE_RESOURCE_MAX_FILES_PER_KIND]
    return limited, len(paths) > len(limited)


def _compact_issue(issue: ScanIssue) -> dict[str, Any]:
    return issue.model_dump(mode="json", exclude_none=True, exclude={"context"})


def build_package_context(settings: ServerSettings, package_name: str) -> str:
    """Build bounded package JSON after safe name-based selection."""
    package_name = validate_package_name(package_name)
    try:
        _, relative_path = resolve_package_selector(
            settings,
            package_name=package_name,
            relative_path=None,
        )
    except PackageSelectionError as exc:
        candidate_text = f" Candidates: {', '.join(exc.candidates)}." if exc.candidates else ""
        raise ResourceError(f"{exc.code}: {exc}.{candidate_text}") from exc

    inspection = inspect_package(settings, relative_path=relative_path)
    manifest = inspection.manifest
    description, description_truncated = _clip(manifest.description if manifest else None)
    path_fields = {
        "launch_files": inspection.launch_files,
        "config_files": inspection.config_files,
        "interface_files": inspection.interface_files,
        "robot_description_files": inspection.robot_description_files,
        "test_files": inspection.test_files,
        "resource_files": inspection.resource_files,
    }
    compact_paths = {}
    reasons = []
    for name, paths in path_fields.items():
        compact, truncated = _compact_paths(paths)
        compact_paths[name] = compact
        if truncated:
            reasons.append(f"{name}_limit")
    if description_truncated:
        reasons.append("description_limit")

    sorted_issues = sorted(
        inspection.issues,
        key=lambda issue: (issue.severity.value, issue.code, issue.path, issue.message),
    )
    returned_issues = sorted_issues[:PACKAGE_RESOURCE_MAX_ISSUES]
    if len(sorted_issues) > len(returned_issues):
        reasons.append("issue_limit")
    severity_counts = {
        severity.value: sum(issue.severity is severity for issue in inspection.issues)
        for severity in Severity
    }
    payload = {
        "name": inspection.name,
        "relative_path": inspection.relative_path,
        "valid": inspection.valid,
        "manifest": {
            "version": manifest.version if manifest else None,
            "description": description,
            "licenses": (
                [license_name[:256] for license_name in manifest.licenses[:20]] if manifest else []
            ),
            "build_type": manifest.build_type if manifest else None,
        },
        "build_system": (
            inspection.build_system.model_dump(mode="json") if inspection.build_system else None
        ),
        "executables": [
            {
                "name": executable.name[:256],
                "target": (executable.target[:512] if executable.target else None),
                "source": executable.source,
                "dynamic": executable.dynamic,
            }
            for executable in inspection.executables[:50]
        ],
        **compact_paths,
        "test_file_count": len(inspection.test_files),
        "issue_severity_counts": severity_counts,
        "issues": [_compact_issue(issue) for issue in returned_issues],
        "detailed_tool_hint": {
            "tool": "inspect_package",
            "arguments": {"package_name": package_name},
        },
        "truncated": bool(reasons),
        "truncation_reason": reasons,
    }
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    if len(text.encode("utf-8")) > PACKAGE_RESOURCE_MAX_JSON_BYTES:
        payload["truncated"] = True
        payload["truncation_reason"] = sorted({*reasons, "json_size_limit"})
        for field_name in path_fields:
            payload[field_name] = payload[field_name][:10]
        payload["executables"] = payload["executables"][:10]
        payload["issues"] = payload["issues"][:10]
        text = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    if len(text.encode("utf-8")) > PACKAGE_RESOURCE_MAX_JSON_BYTES:
        for field_name in path_fields:
            payload[field_name] = []
        payload["executables"] = []
        payload["issues"] = []
        payload["manifest"]["description"] = None
        text = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return text


def register_package_resource(server: FastMCP, settings: ServerSettings) -> None:
    """Register one package-name resource template."""

    @server.resource(
        "ros2-workspace://package/{package_name}",
        name="package-context",
        title="ROS 2 Package Context",
        description="Compact structured context for one uniquely named workspace package.",
        mime_type="application/json",
    )
    def package_context_resource(package_name: str) -> str:
        return build_package_context(settings, package_name)
