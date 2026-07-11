"""Bounded orchestration of all pure workspace analyzers."""

from pathlib import Path

from ros2_workspace_mcp.analyzers.dependencies import analyze_dependencies
from ros2_workspace_mcp.analyzers.interfaces import inspect_interfaces
from ros2_workspace_mcp.analyzers.launch import analyze_launch_file
from ros2_workspace_mcp.analyzers.package import inspect_package
from ros2_workspace_mcp.analyzers.robot import inspect_robot_description
from ros2_workspace_mcp.analyzers.workspace import analyze_workspace
from ros2_workspace_mcp.config import ServerSettings
from ros2_workspace_mcp.models.common import ScanIssue, Severity
from ros2_workspace_mcp.models.diagnosis import DiagnosisSection, WorkspaceDiagnosisResult

MAX_DIAGNOSIS_PACKAGES = 100
MAX_DIAGNOSIS_FILES_PER_KIND = 200
MAX_DIAGNOSIS_ISSUES = 500


def _limit_issue(category: str, limit: int) -> ScanIssue:
    return ScanIssue(
        severity=Severity.WARNING,
        code="ANALYSIS_LIMIT_REACHED",
        message="Diagnosis analysis limit was reached; skipped items are reported.",
        path=".",
        context={"category": category, "limit": limit},
    )


def _deduplicate(issues: list[ScanIssue]) -> list[ScanIssue]:
    unique = {
        (
            issue.code,
            issue.path,
            issue.package_name,
            issue.line,
            issue.column,
            issue.message,
        ): issue
        for issue in issues
    }
    return [
        unique[key] for key in sorted(unique, key=lambda item: tuple(str(part) for part in item))
    ]


def diagnose_workspace(settings: ServerSettings) -> WorkspaceDiagnosisResult:
    """Run all static analyzers with bounded output and no MCP self-calls."""
    scan = analyze_workspace(settings)
    issues = list(scan.issues)
    limits_reached = False
    skipped_files: list[str] = []
    analyzed_files: list[str] = []

    valid_packages = [package for package in scan.packages if package.valid]
    selected_packages = valid_packages[:MAX_DIAGNOSIS_PACKAGES]
    if len(valid_packages) > len(selected_packages):
        limits_reached = True
        skipped_files.extend(
            f"{package.relative_path}/package.xml"
            for package in valid_packages[MAX_DIAGNOSIS_PACKAGES:]
        )
        issues.append(_limit_issue("packages", MAX_DIAGNOSIS_PACKAGES))

    package_valid = 0
    package_invalid = 0
    package_issue_count = 0
    interface_paths: list[tuple[str, str]] = []
    launch_paths: list[str] = []
    robot_paths: list[str] = []
    for package in selected_packages:
        inspection = inspect_package(settings, relative_path=package.relative_path)
        analyzed_files.append(f"{package.relative_path}/package.xml")
        issues.extend(inspection.issues)
        package_issue_count += len(inspection.issues)
        package_valid += inspection.valid
        package_invalid += not inspection.valid
        interface_paths.extend((package.relative_path, path) for path in inspection.interface_files)
        launch_paths.extend(inspection.launch_files)
        robot_paths.extend(inspection.robot_description_files)

    dependency = None
    if len(valid_packages) <= MAX_DIAGNOSIS_PACKAGES:
        dependency = analyze_dependencies(settings)
        issues.extend(dependency.issues)

    interface_paths.sort(key=lambda item: item[1])
    launch_paths = sorted(set(launch_paths))
    robot_paths = sorted(set(robot_paths))
    for category, paths in (
        ("interfaces", [path for _, path in interface_paths]),
        ("launch", launch_paths),
        ("robot_descriptions", robot_paths),
    ):
        if len(paths) > MAX_DIAGNOSIS_FILES_PER_KIND:
            limits_reached = True
            skipped_files.extend(paths[MAX_DIAGNOSIS_FILES_PER_KIND:])
            issues.append(_limit_issue(category, MAX_DIAGNOSIS_FILES_PER_KIND))

    interface_valid = 0
    interface_invalid = 0
    interface_issue_count = 0
    for package_path, interface_path in interface_paths[:MAX_DIAGNOSIS_FILES_PER_KIND]:
        result = inspect_interfaces(
            settings,
            relative_path=package_path,
            interface_name=Path(interface_path).name,
        )
        analyzed_files.append(interface_path)
        issues.extend(result.issues)
        interface_issue_count += len(result.issues)
        for definition in result.interfaces:
            interface_valid += definition.valid
            interface_invalid += not definition.valid

    launch_valid = 0
    launch_invalid = 0
    launch_issue_count = 0
    for launch_path in launch_paths[:MAX_DIAGNOSIS_FILES_PER_KIND]:
        result = analyze_launch_file(settings, relative_path=launch_path)
        analyzed_files.append(launch_path)
        issues.extend(result.issues)
        launch_issue_count += len(result.issues)
        launch_valid += result.valid
        launch_invalid += not result.valid

    robot_valid = 0
    robot_invalid = 0
    robot_issue_count = 0
    for robot_path in robot_paths[:MAX_DIAGNOSIS_FILES_PER_KIND]:
        result = inspect_robot_description(settings, relative_path=robot_path)
        analyzed_files.append(robot_path)
        issues.extend(result.issues)
        robot_issue_count += len(result.issues)
        robot_valid += result.valid
        robot_invalid += not result.valid

    issues = _deduplicate(issues)
    if len(issues) > MAX_DIAGNOSIS_ISSUES:
        limits_reached = True
        issues = issues[: MAX_DIAGNOSIS_ISSUES - 1]
        issues.append(_limit_issue("issues", MAX_DIAGNOSIS_ISSUES))
        issues = _deduplicate(issues)

    errors = [issue for issue in issues if issue.severity is Severity.ERROR]
    warnings = [issue for issue in issues if issue.severity is Severity.WARNING]
    info = [issue for issue in issues if issue.severity is Severity.INFO]
    status = "error" if errors else "warning" if warnings else "ok"
    return WorkspaceDiagnosisResult(
        server_name=settings.server_name,
        server_version=settings.server_version,
        root_path=str(settings.root_path),
        status=status,
        workspace_summary={
            "layout": scan.layout.value,
            "package_count": scan.package_count,
            "valid_package_count": scan.valid_package_count,
            "invalid_package_count": scan.invalid_package_count,
        },
        package_summary=DiagnosisSection(
            analyzed_count=len(selected_packages),
            valid_count=package_valid,
            invalid_count=package_invalid,
            issue_count=package_issue_count,
        ),
        dependency_summary={
            "analyzed": dependency is not None,
            "package_count": len(dependency.packages) if dependency else 0,
            "edge_count": len(dependency.dependency_edges) if dependency else 0,
            "external_dependency_count": len(dependency.external_dependencies) if dependency else 0,
            "cycle_count": len(dependency.cycles) if dependency else 0,
        },
        interface_summary=DiagnosisSection(
            analyzed_count=interface_valid + interface_invalid,
            valid_count=interface_valid,
            invalid_count=interface_invalid,
            issue_count=interface_issue_count,
        ),
        launch_summary=DiagnosisSection(
            analyzed_count=launch_valid + launch_invalid,
            valid_count=launch_valid,
            invalid_count=launch_invalid,
            issue_count=launch_issue_count,
        ),
        robot_description_summary=DiagnosisSection(
            analyzed_count=robot_valid + robot_invalid,
            valid_count=robot_valid,
            invalid_count=robot_invalid,
            issue_count=robot_issue_count,
        ),
        severity_counts={"ERROR": len(errors), "WARNING": len(warnings), "INFO": len(info)},
        errors=errors,
        warnings=warnings,
        info=info,
        analyzed_files=sorted(set(analyzed_files)),
        skipped_files=sorted(set(skipped_files)),
        limits_reached=limits_reached,
        issues=issues,
    )
