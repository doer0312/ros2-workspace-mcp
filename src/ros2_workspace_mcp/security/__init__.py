"""Workspace boundary and input-safety helpers."""

from ros2_workspace_mcp.security.files import (
    DEFAULT_MAX_TEXT_BYTES,
    SafeTextReadError,
    TextFileAccessError,
    TextFileDecodeError,
    TextFileTooLargeError,
    read_text_file_with_limit,
)
from ros2_workspace_mcp.security.paths import (
    InvalidWorkspacePathError,
    PathOutsideRootError,
    WorkspaceSecurityError,
    normalize_workspace_root,
    relative_posix_path,
    resolve_within_root,
)

__all__ = [
    "DEFAULT_MAX_TEXT_BYTES",
    "InvalidWorkspacePathError",
    "PathOutsideRootError",
    "SafeTextReadError",
    "TextFileAccessError",
    "TextFileDecodeError",
    "TextFileTooLargeError",
    "WorkspaceSecurityError",
    "normalize_workspace_root",
    "read_text_file_with_limit",
    "relative_posix_path",
    "resolve_within_root",
]
