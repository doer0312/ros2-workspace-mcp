"""Compact workspace-summary resource."""

import json
from typing import Any

from mcp.server.fastmcp import FastMCP

from ros2_workspace_mcp.analyzers.workspace import analyze_workspace
from ros2_workspace_mcp.config import ServerSettings
from ros2_workspace_mcp.models.common import ScanIssue, Severity

WORKSPACE_RESOURCE_MAX_PACKAGES = 100
WORKSPACE_RESOURCE_MAX_ISSUES = 50


def _issue_sort_key(issue: ScanIssue) -> tuple[int, str, str, str]:
    severity_order = {Severity.ERROR: 0, Severity.WARNING: 1, Severity.INFO: 2}
    return (
        severity_order[issue.severity],
        issue.code,
        issue.path,
        issue.package_name or "",
    )


def _compact_issue(issue: ScanIssue) -> dict[str, Any]:
    return issue.model_dump(mode="json", exclude_none=True, exclude={"context"})


def build_workspace_summary(settings: ServerSettings) -> str:
    """Build deterministic compact JSON only when the resource is read."""
    result = analyze_workspace(settings)
    packages = result.packages[:WORKSPACE_RESOURCE_MAX_PACKAGES]
    key_issues = sorted(
        (issue for issue in result.issues if issue.severity in {Severity.ERROR, Severity.WARNING}),
        key=_issue_sort_key,
    )
    returned_issues = key_issues[:WORKSPACE_RESOURCE_MAX_ISSUES]
    reasons = []
    if len(result.packages) > len(packages):
        reasons.append("package_limit")
    if len(key_issues) > len(returned_issues):
        reasons.append("issue_limit")
    severity_counts = {
        severity.value: sum(issue.severity is severity for issue in result.issues)
        for severity in Severity
    }
    payload = {
        "server_name": result.server_name,
        "server_version": result.server_version,
        "layout": result.layout.value,
        "root_path": result.root_path,
        "package_count": result.package_count,
        "valid_package_count": result.valid_package_count,
        "invalid_package_count": result.invalid_package_count,
        "packages": [
            {
                "name": package.name,
                "relative_path": package.relative_path,
                "build_type": package.build_type,
                "valid": package.valid,
            }
            for package in packages
        ],
        "duplicate_package_names": result.duplicate_package_names,
        "issue_severity_counts": severity_counts,
        "issues": [_compact_issue(issue) for issue in returned_issues],
        "truncated": bool(reasons),
        "truncation_reason": reasons,
        "original_package_count": len(result.packages),
        "original_key_issue_count": len(key_issues),
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def register_workspace_resource(server: FastMCP, settings: ServerSettings) -> None:
    """Register the fixed workspace summary on one server instance."""

    @server.resource(
        "ros2-workspace://summary",
        name="workspace-summary",
        title="ROS 2 Workspace Summary",
        description="Compact, read-only static overview of the configured ROS 2 workspace.",
        mime_type="application/json",
    )
    def workspace_summary_resource() -> str:
        return build_workspace_summary(settings)
