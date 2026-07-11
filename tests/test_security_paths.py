from pathlib import Path

import pytest

from ros2_workspace_mcp.security.paths import (
    InvalidWorkspacePathError,
    PathOutsideRootError,
    normalize_workspace_root,
    resolve_within_root,
)


def test_relative_path_inside_root_succeeds(tmp_path: Path) -> None:
    child = tmp_path / "src"
    child.mkdir()

    assert resolve_within_root(tmp_path, "src") == child.resolve()


def test_absolute_path_inside_root_succeeds(tmp_path: Path) -> None:
    child = tmp_path / "src"
    child.mkdir()

    assert resolve_within_root(tmp_path, child) == child.resolve()


def test_parent_traversal_is_rejected(tmp_path: Path) -> None:
    outside = tmp_path.parent

    with pytest.raises(PathOutsideRootError):
        resolve_within_root(tmp_path, outside)


def test_similar_prefix_directory_is_rejected(tmp_path: Path) -> None:
    root = tmp_path / "ws"
    sibling = tmp_path / "ws-other"
    root.mkdir()
    sibling.mkdir()

    with pytest.raises(PathOutsideRootError):
        resolve_within_root(root, sibling)


def test_nonexistent_path_can_be_resolved_when_allowed(tmp_path: Path) -> None:
    result = resolve_within_root(tmp_path, "future/file.txt", must_exist=False)

    assert result == tmp_path / "future" / "file.txt"


def test_nonexistent_path_is_rejected_by_default(tmp_path: Path) -> None:
    with pytest.raises(InvalidWorkspacePathError):
        resolve_within_root(tmp_path, "missing")


def test_file_and_directory_requirements_are_enforced(tmp_path: Path) -> None:
    file_path = tmp_path / "file"
    directory = tmp_path / "directory"
    file_path.write_text("data", encoding="utf-8")
    directory.mkdir()

    with pytest.raises(InvalidWorkspacePathError, match="not a directory"):
        resolve_within_root(tmp_path, file_path, require_directory=True)
    with pytest.raises(InvalidWorkspacePathError, match="not a regular file"):
        resolve_within_root(tmp_path, directory, require_directory=False)


def test_root_is_canonicalized(tmp_path: Path) -> None:
    nested = tmp_path / "one" / "two"
    nested.mkdir(parents=True)

    assert normalize_workspace_root(nested / ".." / "two") == nested.resolve()


def test_symlink_to_outside_root_is_rejected(tmp_path: Path) -> None:
    root = tmp_path / "root"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    link = root / "escape"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"directory symlinks unavailable on this platform: {exc}")

    with pytest.raises(PathOutsideRootError):
        resolve_within_root(root, link)
