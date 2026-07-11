import json
from collections.abc import Callable
from pathlib import Path

import pytest

from ros2_workspace_mcp.analyzers.workspace import analyze_workspace
from ros2_workspace_mcp.config import ServerSettings
from ros2_workspace_mcp.models.workspace import BuildTypeSource, WorkspaceLayout


def _scan(root: Path):
    return analyze_workspace(ServerSettings(root_path=root))


def test_colcon_workspace_scans_src(tmp_path: Path, write_package: Callable[..., Path]) -> None:
    write_package(tmp_path / "src" / "demo")

    result = _scan(tmp_path)

    assert result.layout is WorkspaceLayout.COLCON_WORKSPACE
    assert result.scan_path == str(tmp_path / "src")
    assert [package.name for package in result.packages] == ["demo_pkg"]


def test_flat_source_directory_is_supported(
    tmp_path: Path, write_package: Callable[..., Path]
) -> None:
    write_package(tmp_path / "demo")

    result = _scan(tmp_path)

    assert result.layout is WorkspaceLayout.SOURCE_DIRECTORY
    assert result.scan_path == str(tmp_path)


def test_multiple_packages_are_sorted_stably(
    tmp_path: Path, write_package: Callable[..., Path]
) -> None:
    write_package(tmp_path / "src" / "z", name="z_pkg")
    write_package(tmp_path / "src" / "a", name="a_pkg")

    first = _scan(tmp_path)
    second = _scan(tmp_path)

    assert [package.name for package in first.packages] == ["a_pkg", "z_pkg"]
    assert first.model_dump(mode="json") == second.model_dump(mode="json")


def test_nested_package_is_not_scanned_twice(
    tmp_path: Path, write_package: Callable[..., Path]
) -> None:
    outer = write_package(tmp_path / "src" / "outer", name="outer")
    write_package(outer / "nested", name="nested")

    result = _scan(tmp_path)

    assert [package.name for package in result.packages] == ["outer"]


@pytest.mark.parametrize("marker", ["COLCON_IGNORE", "AMENT_IGNORE", "CATKIN_IGNORE"])
def test_ignore_markers_skip_subtree(
    tmp_path: Path, write_package: Callable[..., Path], marker: str
) -> None:
    ignored = tmp_path / "src" / "ignored"
    ignored.mkdir(parents=True)
    (ignored / marker).touch()
    write_package(ignored / "pkg")

    result = _scan(tmp_path)

    assert result.package_count == 0
    assert any(issue.code == "IGNORED_DIRECTORY" for issue in result.issues)


def test_build_directories_are_ignored_globally(
    tmp_path: Path, write_package: Callable[..., Path]
) -> None:
    write_package(tmp_path / "src" / "build" / "generated")
    write_package(tmp_path / "src" / "real", name="real")

    assert [package.name for package in _scan(tmp_path).packages] == ["real"]


def test_duplicate_names_are_reported_for_each_package(
    tmp_path: Path, write_package: Callable[..., Path]
) -> None:
    write_package(tmp_path / "src" / "one", name="duplicate")
    write_package(tmp_path / "src" / "two", name="duplicate")

    result = _scan(tmp_path)

    assert result.duplicate_package_names == ["duplicate"]
    assert all(
        any(issue.code == "DUPLICATE_PACKAGE_NAME" for issue in package.issues)
        for package in result.packages
    )


def test_empty_workspace_returns_warning(tmp_path: Path) -> None:
    result = _scan(tmp_path)

    assert result.package_count == 0
    assert result.packages == []
    assert any(issue.code == "NO_ROS_PACKAGES_FOUND" for issue in result.issues)


def test_broken_manifest_does_not_hide_valid_package(
    tmp_path: Path, write_package: Callable[..., Path]
) -> None:
    broken = tmp_path / "src" / "broken"
    broken.mkdir(parents=True)
    (broken / "package.xml").write_text("<package>", encoding="utf-8")
    write_package(tmp_path / "src" / "valid", name="valid")

    result = _scan(tmp_path)

    assert result.package_count == 2
    assert result.valid_package_count == 1
    assert result.invalid_package_count == 1
    assert any(issue.code == "INVALID_PACKAGE_XML" for issue in result.issues)


def test_missing_required_manifest_field_makes_candidate_invalid(tmp_path: Path) -> None:
    package = tmp_path / "pkg"
    package.mkdir()
    (package / "package.xml").write_text(
        "<package><version>1.0.0</version><description>demo</description>"
        "<maintainer>Dev</maintainer><license>MIT</license></package>",
        encoding="utf-8",
    )

    result = _scan(tmp_path)

    assert result.invalid_package_count == 1
    assert any(issue.code == "MISSING_PACKAGE_NAME" for issue in result.issues)


def test_relative_package_paths_are_posix_and_inside_root(
    tmp_path: Path, write_package: Callable[..., Path]
) -> None:
    write_package(tmp_path / "src" / "group" / "demo")

    package = _scan(tmp_path).packages[0]

    assert package.relative_path == "src/group/demo"
    assert "\\" not in package.relative_path
    assert (tmp_path / Path(package.relative_path)).resolve().is_relative_to(tmp_path.resolve())


def test_result_is_json_serializable(tmp_path: Path, write_package: Callable[..., Path]) -> None:
    write_package(tmp_path / "pkg")

    json.dumps(_scan(tmp_path).model_dump(mode="json"))


def test_build_type_is_inferred_from_cmake(
    tmp_path: Path, write_package: Callable[..., Path]
) -> None:
    package = write_package(tmp_path / "pkg")
    (package / "CMakeLists.txt").touch()

    summary = _scan(tmp_path).packages[0]

    assert summary.build_type == "ament_cmake"
    assert summary.build_type_source is BuildTypeSource.INFERRED


def test_build_type_is_inferred_from_python(
    tmp_path: Path, write_package: Callable[..., Path]
) -> None:
    package = write_package(tmp_path / "pkg")
    (package / "setup.cfg").touch()

    summary = _scan(tmp_path).packages[0]

    assert summary.build_type == "ament_python"
    assert summary.build_type_source is BuildTypeSource.INFERRED


def test_ambiguous_build_markers_remain_unknown(
    tmp_path: Path, write_package: Callable[..., Path]
) -> None:
    package = write_package(tmp_path / "pkg")
    (package / "CMakeLists.txt").touch()
    (package / "setup.py").touch()

    summary = _scan(tmp_path).packages[0]

    assert summary.build_type == "unknown"
    assert summary.build_type_source is BuildTypeSource.UNKNOWN
    assert any(issue.code == "AMBIGUOUS_BUILD_TYPE" for issue in summary.issues)


def test_manifest_build_type_takes_precedence(
    tmp_path: Path, write_package: Callable[..., Path]
) -> None:
    package = write_package(tmp_path / "pkg", build_type="ament_python")
    (package / "CMakeLists.txt").touch()

    summary = _scan(tmp_path).packages[0]

    assert summary.build_type == "ament_python"
    assert summary.build_type_source is BuildTypeSource.MANIFEST


def test_directory_symlink_outside_root_is_skipped_with_warning(tmp_path: Path) -> None:
    root = tmp_path / "root"
    source = root / "src"
    outside = tmp_path / "outside"
    source.mkdir(parents=True)
    outside.mkdir()
    link = source / "escape"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"directory symlinks unavailable on this platform: {exc}")

    result = _scan(root)

    assert result.package_count == 0
    assert any(issue.code == "SYMLINK_OUTSIDE_ROOT" for issue in result.issues)
