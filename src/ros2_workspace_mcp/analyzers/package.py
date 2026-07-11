"""Detailed read-only package inspection."""

import configparser
import os
from pathlib import Path

from ros2_workspace_mcp.analyzers.package_selector import (
    PackageSelectionError,
    resolve_package_selector,
)
from ros2_workspace_mcp.config import ServerSettings
from ros2_workspace_mcp.models.common import ScanIssue, Severity
from ros2_workspace_mcp.models.package import (
    BuildSystemInspection,
    ExecutableSummary,
    PackageInspectionResult,
    PackageManifestDetails,
)
from ros2_workspace_mcp.models.workspace import BuildTypeSource
from ros2_workspace_mcp.parsers.build_files import (
    parse_cmake_executables,
    parse_setup_cfg_executables,
    parse_setup_py_executables,
)
from ros2_workspace_mcp.parsers.package_details import parse_package_manifest_details
from ros2_workspace_mcp.parsers.package_xml import PackageXmlError
from ros2_workspace_mcp.security.files import SafeTextReadError
from ros2_workspace_mcp.security.paths import (
    InvalidWorkspacePathError,
    PathOutsideRootError,
    resolve_within_root,
)

_IGNORED = frozenset({".git", ".venv", "__pycache__", "build", "install", "log"})
_LAUNCH_SUFFIXES = (".launch.py", ".launch.xml", ".launch.yaml", ".launch.yml")


def _issue(
    severity: Severity,
    code: str,
    message: str,
    path: str,
    package_name: str | None = None,
) -> ScanIssue:
    return ScanIssue(
        severity=severity,
        code=code,
        message=message,
        path=path,
        package_name=package_name,
    )


def _selection_error(error: PackageSelectionError) -> PackageInspectionResult:
    return PackageInspectionResult(
        name=None,
        relative_path=None,
        valid=False,
        manifest=None,
        build_system=None,
        selection_candidates=error.candidates,
        issues=[_issue(Severity.ERROR, error.code, str(error), ".")],
    )


def _safe_file(root: Path, path: Path) -> bool:
    try:
        resolve_within_root(root, path, require_directory=False)
    except (InvalidWorkspacePathError, PathOutsideRootError):
        return False
    return True


def _classify_files(
    root: Path,
    package_dir: Path,
    package_name: str | None,
    issues: list[ScanIssue],
) -> dict[str, list[str]]:
    classified = {
        "launch_files": [],
        "config_files": [],
        "interface_files": [],
        "robot_description_files": [],
        "test_files": [],
        "resource_files": [],
    }

    def walk(directory: Path) -> None:
        try:
            with os.scandir(directory) as iterator:
                entries = sorted(iterator, key=lambda item: (item.name.casefold(), item.name))
        except OSError:
            issues.append(
                _issue(
                    Severity.WARNING,
                    "DIRECTORY_READ_ERROR",
                    "Package directory could not be listed.",
                    directory.relative_to(root).as_posix(),
                    package_name,
                )
            )
            return
        for entry in entries:
            path = directory / entry.name
            relative_package = path.relative_to(package_dir)
            relative_root = path.relative_to(root).as_posix()
            if entry.is_symlink():
                try:
                    safe = resolve_within_root(root, path)
                except (InvalidWorkspacePathError, PathOutsideRootError):
                    issues.append(
                        _issue(
                            Severity.WARNING,
                            "SYMLINK_OUTSIDE_ROOT",
                            "Symbolic link was skipped because its target is unsafe.",
                            relative_root,
                            package_name,
                        )
                    )
                    continue
                if safe.is_dir():
                    continue
            try:
                if entry.is_dir(follow_symlinks=False):
                    if entry.name not in _IGNORED:
                        walk(path)
                    continue
                if not resolve_within_root(root, path, require_directory=False).is_file():
                    continue
            except (OSError, InvalidWorkspacePathError, PathOutsideRootError):
                continue

            parts = relative_package.parts
            suffix = path.suffix.casefold()
            if entry.name.casefold().endswith(_LAUNCH_SUFFIXES):
                classified["launch_files"].append(relative_root)
            if parts and parts[0] == "config" and suffix in {".yaml", ".yml"}:
                classified["config_files"].append(relative_root)
            if (
                parts
                and parts[0] in {"msg", "srv", "action"}
                and suffix
                in {
                    ".msg",
                    ".srv",
                    ".action",
                }
            ):
                classified["interface_files"].append(relative_root)
            if parts and parts[0] in {"urdf", "description"} and suffix in {".urdf", ".xacro"}:
                classified["robot_description_files"].append(relative_root)
            if (
                any(part in {"test", "tests"} for part in parts[:-1])
                or entry.name.startswith("test_")
                or entry.name.endswith("_test.py")
            ):
                classified["test_files"].append(relative_root)
            if parts and parts[0] in {"resource", "rviz", "meshes"}:
                classified["resource_files"].append(relative_root)

    walk(package_dir)
    for paths in classified.values():
        paths.sort()
    return classified


def _build_system(
    manifest: PackageManifestDetails | None, root: Path, package_dir: Path
) -> BuildSystemInspection:
    has_cmake = _safe_file(root, package_dir / "CMakeLists.txt")
    has_setup_py = _safe_file(root, package_dir / "setup.py")
    has_setup_cfg = _safe_file(root, package_dir / "setup.cfg")
    has_pyproject = _safe_file(root, package_dir / "pyproject.toml")
    has_python = has_setup_py or has_setup_cfg or has_pyproject
    evidence = sorted(
        name
        for present, name in (
            (has_cmake, "CMakeLists.txt"),
            (has_setup_py, "setup.py"),
            (has_setup_cfg, "setup.cfg"),
            (has_pyproject, "pyproject.toml"),
        )
        if present
    )
    manifest_type = manifest.build_type if manifest else None
    conflict = has_cmake and has_python
    if manifest_type:
        inferred = manifest_type
        source = BuildTypeSource.MANIFEST
    elif conflict or not (has_cmake or has_python):
        inferred = "unknown"
        source = BuildTypeSource.UNKNOWN
    elif has_cmake:
        inferred = "ament_cmake"
        source = BuildTypeSource.INFERRED
    else:
        inferred = "ament_python"
        source = BuildTypeSource.INFERRED
    return BuildSystemInspection(
        manifest_build_type=manifest_type,
        inferred_build_type=inferred,
        build_type_source=source,
        evidence=evidence,
        conflict=conflict,
        has_cmake_lists=has_cmake,
        has_setup_py=has_setup_py,
        has_setup_cfg=has_setup_cfg,
        has_pyproject_toml=has_pyproject,
    )


def _executables(
    root: Path,
    package_dir: Path,
    package_name: str | None,
    build: BuildSystemInspection,
    issues: list[ScanIssue],
) -> list[ExecutableSummary]:
    result: list[ExecutableSummary] = []
    parsers = (
        (build.has_setup_py, "setup.py", parse_setup_py_executables),
        (build.has_setup_cfg, "setup.cfg", parse_setup_cfg_executables),
        (build.has_cmake_lists, "CMakeLists.txt", parse_cmake_executables),
    )
    for present, filename, parser in parsers:
        if not present:
            continue
        try:
            parsed = parser(root, package_dir / filename)
            entries, dynamic = parsed if isinstance(parsed, tuple) else (parsed, False)
            result.extend(entries)
            if dynamic:
                issues.append(
                    _issue(
                        Severity.WARNING,
                        "DYNAMIC_BUILD_EXPRESSION",
                        f"{filename} contains build expressions that were not evaluated.",
                        (package_dir / filename).relative_to(root).as_posix(),
                        package_name,
                    )
                )
        except (SafeTextReadError, SyntaxError, configparser.Error, ValueError) as exc:
            issues.append(
                _issue(
                    Severity.WARNING,
                    "BUILD_FILE_PARSE_ERROR",
                    f"{filename} could not be parsed statically: {type(exc).__name__}.",
                    (package_dir / filename).relative_to(root).as_posix(),
                    package_name,
                )
            )
    unique = {(item.name, item.target, item.source): item for item in result}
    return sorted(unique.values(), key=lambda item: (item.name, item.source, item.target or ""))


def inspect_package(
    settings: ServerSettings,
    *,
    package_name: str | None = None,
    relative_path: str | None = None,
) -> PackageInspectionResult:
    """Inspect one package without importing or executing workspace code."""
    try:
        package_dir, selected_relative = resolve_package_selector(
            settings,
            package_name=package_name,
            relative_path=relative_path,
        )
    except PackageSelectionError as exc:
        return _selection_error(exc)

    issues: list[ScanIssue] = []
    manifest: PackageManifestDetails | None = None
    try:
        manifest = parse_package_manifest_details(settings.root_path, package_dir / "package.xml")
    except PackageXmlError as exc:
        issues.append(
            _issue(
                Severity.ERROR,
                "INVALID_PACKAGE_XML",
                str(exc),
                f"{selected_relative}/package.xml",
            )
        )

    name = manifest.name if manifest else None
    if manifest is not None:
        required = (
            (manifest.name, "MISSING_PACKAGE_NAME"),
            (manifest.version, "MISSING_PACKAGE_VERSION"),
            (manifest.description, "MISSING_PACKAGE_DESCRIPTION"),
            (manifest.maintainers, "MISSING_PACKAGE_MAINTAINER"),
            (manifest.licenses, "MISSING_PACKAGE_LICENSE"),
        )
        for value, code in required:
            if not value:
                issues.append(
                    _issue(
                        Severity.ERROR,
                        code,
                        "Required package.xml metadata is missing.",
                        f"{selected_relative}/package.xml",
                        name,
                    )
                )

    build = _build_system(manifest, settings.root_path, package_dir)
    if build.conflict:
        issues.append(
            _issue(
                Severity.WARNING,
                "BUILD_SYSTEM_CONFLICT",
                "Both CMake and Python build-system files are present.",
                selected_relative,
                name,
            )
        )
    executables = _executables(settings.root_path, package_dir, name, build, issues)
    classified = _classify_files(settings.root_path, package_dir, name, issues)
    return PackageInspectionResult(
        name=name,
        relative_path=selected_relative,
        valid=manifest is not None
        and not any(issue.severity is Severity.ERROR for issue in issues),
        manifest=manifest,
        build_system=build,
        executables=executables,
        issues=issues,
        **classified,
    )
