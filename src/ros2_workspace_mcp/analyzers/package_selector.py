"""Shared unambiguous package selection for package-scoped tools."""

from pathlib import Path

from ros2_workspace_mcp.analyzers.workspace import analyze_workspace
from ros2_workspace_mcp.config import ServerSettings
from ros2_workspace_mcp.security.paths import (
    InvalidWorkspacePathError,
    PathOutsideRootError,
    resolve_within_root,
)


class PackageSelectionError(Exception):
    """A stable package-selector failure suitable for a tool issue."""

    def __init__(self, code: str, message: str, candidates: list[str] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.candidates = candidates or []


def resolve_package_selector(
    settings: ServerSettings,
    *,
    package_name: str | None,
    relative_path: str | None,
) -> tuple[Path, str]:
    """Resolve exactly one package selector to a safe package directory."""
    if (package_name is None) == (relative_path is None):
        raise PackageSelectionError(
            "INVALID_PACKAGE_SELECTOR",
            "Provide exactly one of package_name or relative_path.",
        )

    if package_name is not None:
        matches = [
            package.relative_path
            for package in analyze_workspace(settings).packages
            if package.name == package_name
        ]
        if not matches:
            raise PackageSelectionError(
                "PACKAGE_NOT_FOUND", "No package with the requested name was found."
            )
        if len(matches) > 1:
            raise PackageSelectionError(
                "AMBIGUOUS_PACKAGE_NAME",
                "Multiple packages have this name; select one with relative_path.",
                sorted(matches),
            )
        relative_path = matches[0]

    try:
        package_dir = resolve_within_root(
            settings.root_path,
            relative_path or "",
            require_directory=True,
        )
        resolve_within_root(
            settings.root_path,
            package_dir / "package.xml",
            require_directory=False,
        )
    except PathOutsideRootError as exc:
        raise PackageSelectionError(
            "PATH_OUTSIDE_ROOT", "Package path resolves outside the configured workspace."
        ) from exc
    except InvalidWorkspacePathError as exc:
        raise PackageSelectionError(
            "INVALID_PACKAGE_PATH", "Package directory or package.xml is not accessible."
        ) from exc

    return package_dir, package_dir.relative_to(settings.root_path).as_posix() or "."
