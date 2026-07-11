"""Canonical path checks for read-only workspace access."""

from pathlib import Path
from typing import Any


class WorkspaceSecurityError(Exception):
    """Base class for workspace sandbox violations."""


class PathOutsideRootError(WorkspaceSecurityError):
    """Raised when a path resolves outside the configured workspace."""


class InvalidWorkspacePathError(WorkspaceSecurityError):
    """Raised when a workspace path is missing or has the wrong type."""


def normalize_workspace_root(value: Any) -> Path:
    """Return an existing, canonical workspace directory."""
    try:
        path = Path(value).expanduser().resolve(strict=True)
    except (FileNotFoundError, OSError, TypeError) as exc:
        raise InvalidWorkspacePathError(f"workspace root does not exist: {value}") from exc
    if not path.is_dir():
        raise InvalidWorkspacePathError(f"workspace root is not a directory: {path}")
    return path


def resolve_within_root(
    root: Path,
    candidate: str | Path,
    *,
    must_exist: bool = True,
    require_directory: bool | None = None,
) -> Path:
    """Resolve a candidate while enforcing containment in a canonical root."""
    canonical_root = normalize_workspace_root(root)
    raw_candidate = Path(candidate).expanduser()
    unresolved = raw_candidate if raw_candidate.is_absolute() else canonical_root / raw_candidate

    resolved = unresolved.resolve(strict=False)
    try:
        contained = resolved.is_relative_to(canonical_root)
    except ValueError:
        contained = False
    if not contained:
        raise PathOutsideRootError("path resolves outside the configured workspace")

    if must_exist:
        try:
            resolved = unresolved.resolve(strict=True)
        except (FileNotFoundError, OSError) as exc:
            raise InvalidWorkspacePathError("workspace path does not exist") from exc
        try:
            contained = resolved.is_relative_to(canonical_root)
        except ValueError:
            contained = False
        if not contained:
            raise PathOutsideRootError("path resolves outside the configured workspace")

    if must_exist or resolved.exists():
        if require_directory is True and not resolved.is_dir():
            raise InvalidWorkspacePathError("workspace path is not a directory")
        if require_directory is False and not resolved.is_file():
            raise InvalidWorkspacePathError("workspace path is not a regular file")
    return resolved


def relative_posix_path(root: Path, path: Path) -> str:
    """Return a stable, workspace-relative POSIX path after containment validation."""
    resolved = resolve_within_root(root, path)
    relative = resolved.relative_to(normalize_workspace_root(root))
    return relative.as_posix() or "."
