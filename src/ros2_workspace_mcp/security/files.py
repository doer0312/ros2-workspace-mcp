"""Shared bounded text reading inside the workspace sandbox."""

from pathlib import Path

from ros2_workspace_mcp.security.paths import resolve_within_root

DEFAULT_MAX_TEXT_BYTES = 1024 * 1024


class SafeTextReadError(Exception):
    """Base class for safe text-read failures."""


class TextFileTooLargeError(SafeTextReadError):
    """Raised before reading a file above the configured size limit."""


class TextFileDecodeError(SafeTextReadError):
    """Raised when a file is not UTF-8 text."""


class TextFileAccessError(SafeTextReadError):
    """Raised when an otherwise safe file cannot be read."""


def read_text_file_with_limit(
    root: Path,
    candidate: str | Path,
    *,
    max_bytes: int = DEFAULT_MAX_TEXT_BYTES,
) -> str:
    """Read UTF-8 or UTF-8-BOM text after sandbox and size validation."""
    safe_path = resolve_within_root(root, candidate, require_directory=False)
    try:
        if safe_path.stat().st_size > max_bytes:
            raise TextFileTooLargeError(f"text file exceeds the {max_bytes}-byte safety limit")
        data = safe_path.read_bytes()
    except TextFileTooLargeError:
        raise
    except OSError as exc:
        raise TextFileAccessError("text file could not be read") from exc
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise TextFileDecodeError("text file is not valid UTF-8") from exc
