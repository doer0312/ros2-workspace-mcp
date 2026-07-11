"""Compact models for full-workspace diagnosis."""

from typing import Any

from pydantic import BaseModel, Field

from ros2_workspace_mcp.models.common import ScanIssue


class DiagnosisSection(BaseModel):
    """Counts for one diagnosis analysis section."""

    analyzed_count: int = 0
    valid_count: int = 0
    invalid_count: int = 0
    issue_count: int = 0


class WorkspaceDiagnosisResult(BaseModel):
    """Bounded, deduplicated diagnosis summary."""

    server_name: str
    server_version: str
    root_path: str
    status: str
    workspace_summary: dict[str, Any]
    package_summary: DiagnosisSection
    dependency_summary: dict[str, Any]
    interface_summary: DiagnosisSection
    launch_summary: DiagnosisSection
    robot_description_summary: DiagnosisSection
    severity_counts: dict[str, int]
    errors: list[ScanIssue] = Field(default_factory=list)
    warnings: list[ScanIssue] = Field(default_factory=list)
    info: list[ScanIssue] = Field(default_factory=list)
    analyzed_files: list[str] = Field(default_factory=list)
    skipped_files: list[str] = Field(default_factory=list)
    limits_reached: bool = False
    issues: list[ScanIssue] = Field(default_factory=list)
