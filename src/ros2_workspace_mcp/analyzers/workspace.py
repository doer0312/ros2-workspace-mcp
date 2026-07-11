"""Read-only ROS 2 workspace package discovery."""

import os
from pathlib import Path

from ros2_workspace_mcp.config import ServerSettings
from ros2_workspace_mcp.models.common import ScanIssue, Severity
from ros2_workspace_mcp.models.workspace import (
    BuildTypeSource,
    PackageManifest,
    PackageSummary,
    WorkspaceLayout,
    WorkspaceScanResult,
)
from ros2_workspace_mcp.parsers.package_xml import PackageXmlError, parse_package_xml
from ros2_workspace_mcp.security.paths import (
    InvalidWorkspacePathError,
    PathOutsideRootError,
    resolve_within_root,
)

IGNORED_DIRECTORY_NAMES = frozenset(
    {
        ".git",
        ".github",
        ".idea",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".venv",
        ".vscode",
        "__pycache__",
        "build",
        "dist",
        "env",
        "install",
        "log",
        "node_modules",
        "venv",
    }
)
IGNORE_MARKERS = frozenset({"AMENT_IGNORE", "CATKIN_IGNORE", "COLCON_IGNORE"})


def _relative(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix() or "."


def _issue(
    severity: Severity,
    code: str,
    message: str,
    root: Path,
    path: Path,
    package_name: str | None = None,
) -> ScanIssue:
    return ScanIssue(
        severity=severity,
        code=code,
        message=message,
        path=_relative(root, path),
        package_name=package_name,
    )


def _entries(root: Path, directory: Path, issues: list[ScanIssue]) -> list[os.DirEntry[str]]:
    try:
        with os.scandir(directory) as iterator:
            return sorted(iterator, key=lambda entry: (entry.name.casefold(), entry.name))
    except PermissionError:
        issues.append(
            _issue(
                Severity.ERROR,
                "PERMISSION_DENIED",
                "Directory could not be read; scanning continued elsewhere.",
                root,
                directory,
            )
        )
    except OSError:
        issues.append(
            _issue(
                Severity.WARNING,
                "DIRECTORY_READ_ERROR",
                "Directory could not be inspected; scanning continued elsewhere.",
                root,
                directory,
            )
        )
    return []


def _safe_file_exists(root: Path, candidate: Path, package_issues: list[ScanIssue]) -> bool:
    try:
        resolve_within_root(root, candidate, require_directory=False)
    except PathOutsideRootError:
        package_issues.append(
            _issue(
                Severity.WARNING,
                "SYMLINK_OUTSIDE_ROOT",
                "Symbolic link resolves outside the workspace and was skipped.",
                root,
                candidate,
            )
        )
        return False
    except InvalidWorkspacePathError:
        return False
    return True


def _missing_field_issues(
    manifest: PackageManifest, root: Path, package_dir: Path
) -> list[ScanIssue]:
    fields = (
        (manifest.name, "MISSING_PACKAGE_NAME", "package.xml is missing a package name."),
        (manifest.version, "MISSING_PACKAGE_VERSION", "package.xml is missing a version."),
        (
            manifest.description,
            "MISSING_PACKAGE_DESCRIPTION",
            "package.xml is missing a description.",
        ),
        (
            manifest.maintainer_count,
            "MISSING_PACKAGE_MAINTAINER",
            "package.xml is missing a non-empty maintainer.",
        ),
        (
            manifest.licenses,
            "MISSING_PACKAGE_LICENSE",
            "package.xml is missing a non-empty license.",
        ),
    )
    return [
        _issue(Severity.ERROR, code, message, root, package_dir / "package.xml", manifest.name)
        for value, code, message in fields
        if not value
    ]


def _build_type(
    manifest: PackageManifest | None,
    *,
    has_cmake_lists: bool,
    has_setup_py: bool,
    has_setup_cfg: bool,
    root: Path,
    package_dir: Path,
) -> tuple[str, BuildTypeSource, list[ScanIssue]]:
    if manifest is not None and manifest.build_type:
        return manifest.build_type, BuildTypeSource.MANIFEST, []

    has_python_build = has_setup_py or has_setup_cfg
    if has_cmake_lists and has_python_build:
        issue = _issue(
            Severity.WARNING,
            "AMBIGUOUS_BUILD_TYPE",
            "Both CMake and Python build markers exist; build type remains unknown.",
            root,
            package_dir,
            manifest.name if manifest else None,
        )
        return "unknown", BuildTypeSource.UNKNOWN, [issue]
    if has_cmake_lists:
        return "ament_cmake", BuildTypeSource.INFERRED, []
    if has_python_build:
        return "ament_python", BuildTypeSource.INFERRED, []
    issue = _issue(
        Severity.WARNING,
        "UNKNOWN_BUILD_TYPE",
        "No manifest build type or recognized build marker was found.",
        root,
        package_dir,
        manifest.name if manifest else None,
    )
    return "unknown", BuildTypeSource.UNKNOWN, [issue]


def _summarize_package(root: Path, package_dir: Path) -> PackageSummary:
    manifest_path = package_dir / "package.xml"
    package_issues: list[ScanIssue] = []
    manifest: PackageManifest | None = None
    try:
        manifest = parse_package_xml(root, manifest_path)
    except PathOutsideRootError:
        package_issues.append(
            _issue(
                Severity.ERROR,
                "SYMLINK_OUTSIDE_ROOT",
                "package.xml resolves outside the configured workspace and was not read.",
                root,
                manifest_path,
            )
        )
    except InvalidWorkspacePathError:
        package_issues.append(
            _issue(
                Severity.ERROR,
                "INVALID_PACKAGE_XML",
                "package.xml is not a readable regular file.",
                root,
                manifest_path,
            )
        )
    except PackageXmlError as exc:
        package_issues.append(
            _issue(
                Severity.ERROR,
                "INVALID_PACKAGE_XML",
                str(exc),
                root,
                manifest_path,
            )
        )

    has_cmake_lists = _safe_file_exists(root, package_dir / "CMakeLists.txt", package_issues)
    has_setup_py = _safe_file_exists(root, package_dir / "setup.py", package_issues)
    has_setup_cfg = _safe_file_exists(root, package_dir / "setup.cfg", package_issues)
    if manifest is not None:
        package_issues.extend(_missing_field_issues(manifest, root, package_dir))

    build_type, build_type_source, build_issues = _build_type(
        manifest,
        has_cmake_lists=has_cmake_lists,
        has_setup_py=has_setup_py,
        has_setup_cfg=has_setup_cfg,
        root=root,
        package_dir=package_dir,
    )
    package_issues.extend(build_issues)

    return PackageSummary(
        name=manifest.name if manifest else None,
        relative_path=_relative(root, package_dir),
        version=manifest.version if manifest else None,
        description=manifest.description if manifest else None,
        package_format=manifest.package_format if manifest else None,
        build_type=build_type,
        build_type_source=build_type_source,
        maintainer_count=manifest.maintainer_count if manifest else 0,
        licenses=manifest.licenses if manifest else [],
        has_cmake_lists=has_cmake_lists,
        has_setup_py=has_setup_py,
        has_setup_cfg=has_setup_cfg,
        valid=manifest is not None
        and not any(issue.severity is Severity.ERROR for issue in package_issues),
        issues=package_issues,
    )


def _scan_directory(
    root: Path,
    directory: Path,
    packages: list[PackageSummary],
    issues: list[ScanIssue],
) -> None:
    entries = _entries(root, directory, issues)
    names = {entry.name for entry in entries}
    markers = sorted(names & IGNORE_MARKERS)
    if markers:
        issues.append(
            _issue(
                Severity.INFO,
                "IGNORED_DIRECTORY",
                f"Directory skipped because it contains {', '.join(markers)}.",
                root,
                directory,
            )
        )
        return

    if "package.xml" in names:
        packages.append(_summarize_package(root, directory))
        return

    for entry in entries:
        entry_path = directory / entry.name
        if entry.is_symlink():
            try:
                resolve_within_root(root, entry_path)
            except PathOutsideRootError:
                issues.append(
                    _issue(
                        Severity.WARNING,
                        "SYMLINK_OUTSIDE_ROOT",
                        "Symbolic link resolves outside the workspace and was skipped.",
                        root,
                        entry_path,
                    )
                )
            except InvalidWorkspacePathError:
                issues.append(
                    _issue(
                        Severity.WARNING,
                        "INVALID_SYMLINK",
                        "Broken or inaccessible symbolic link was skipped.",
                        root,
                        entry_path,
                    )
                )
            continue
        if entry.name in IGNORED_DIRECTORY_NAMES:
            continue
        try:
            is_directory = entry.is_dir(follow_symlinks=False)
        except OSError:
            issues.append(
                _issue(
                    Severity.WARNING,
                    "PATH_INSPECTION_ERROR",
                    "Path type could not be determined and was skipped.",
                    root,
                    entry_path,
                )
            )
            continue
        if is_directory:
            _scan_directory(root, entry_path, packages, issues)


def _add_duplicate_issues(
    root: Path, packages: list[PackageSummary], issues: list[ScanIssue]
) -> list[str]:
    by_name: dict[str, list[PackageSummary]] = {}
    for package in packages:
        if package.valid and package.name:
            by_name.setdefault(package.name, []).append(package)

    duplicates = sorted(name for name, matches in by_name.items() if len(matches) > 1)
    for name in duplicates:
        for package in by_name[name]:
            issue = _issue(
                Severity.WARNING,
                "DUPLICATE_PACKAGE_NAME",
                f"Multiple valid packages use the name {name!r}.",
                root,
                root / package.relative_path,
                name,
            )
            package.issues.append(issue)
            issues.append(issue)
    return duplicates


def analyze_workspace(settings: ServerSettings) -> WorkspaceScanResult:
    """Scan the configured workspace without executing or modifying it."""
    root = settings.root_path
    source_candidate = root / "src"
    if not source_candidate.is_symlink() and source_candidate.is_dir():
        scan_path = resolve_within_root(root, source_candidate, require_directory=True)
        layout = WorkspaceLayout.COLCON_WORKSPACE
    else:
        scan_path = root
        layout = WorkspaceLayout.SOURCE_DIRECTORY

    packages: list[PackageSummary] = []
    issues: list[ScanIssue] = []
    _scan_directory(root, scan_path, packages, issues)
    packages.sort(key=lambda package: ((package.name or "").casefold(), package.relative_path))

    for package in packages:
        issues.extend(package.issues)
    duplicate_names = _add_duplicate_issues(root, packages, issues)
    if not packages:
        issues.append(
            _issue(
                Severity.WARNING,
                "NO_ROS_PACKAGES_FOUND",
                "No ROS packages were found in the source scan directory.",
                root,
                scan_path,
            )
        )

    valid_count = sum(package.valid for package in packages)
    return WorkspaceScanResult(
        server_name=settings.server_name,
        server_version=settings.server_version,
        root_path=str(root),
        scan_path=str(scan_path),
        layout=layout,
        package_count=len(packages),
        valid_package_count=valid_count,
        invalid_package_count=len(packages) - valid_count,
        packages=packages,
        duplicate_package_names=duplicate_names,
        issues=issues,
    )
