import json
from collections.abc import Callable
from pathlib import Path

from ros2_workspace_mcp.analyzers.dependencies import analyze_dependencies
from ros2_workspace_mcp.config import ServerSettings


def _add_dependencies(package: Path, declarations: str) -> None:
    manifest = package / "package.xml"
    text = manifest.read_text(encoding="utf-8")
    manifest.write_text(text.replace("</package>", f"{declarations}</package>"), encoding="utf-8")


def test_workspace_and_external_dependencies(
    tmp_path: Path, write_package: Callable[..., Path]
) -> None:
    core = write_package(tmp_path / "src" / "core", name="core")
    app = write_package(tmp_path / "src" / "app", name="app")
    _add_dependencies(app, "<depend>core</depend><exec_depend>rclpy</exec_depend>")

    result = analyze_dependencies(ServerSettings(root_path=tmp_path))

    assert result.workspace_dependencies == ["core"]
    assert result.external_dependencies == ["rclpy"]
    assert result.missing_workspace_references == []
    assert result.topological_order == ["core", "app"]
    assert result.dependency_edges[0].kinds == ["depend"]
    assert core.exists()
    json.dumps(result.model_dump(mode="json"))


def test_branched_topological_order(tmp_path: Path, write_package: Callable[..., Path]) -> None:
    write_package(tmp_path / "src" / "base", name="base")
    left = write_package(tmp_path / "src" / "left", name="left")
    right = write_package(tmp_path / "src" / "right", name="right")
    _add_dependencies(left, "<depend>base</depend>")
    _add_dependencies(right, "<build_depend>base</build_depend>")

    result = analyze_dependencies(ServerSettings(root_path=tmp_path))

    assert result.topological_order[0] == "base"
    assert set(result.topological_order[1:]) == {"left", "right"}


def test_cycle_and_self_dependency_are_reported(
    tmp_path: Path, write_package: Callable[..., Path]
) -> None:
    one = write_package(tmp_path / "src" / "one", name="one")
    two = write_package(tmp_path / "src" / "two", name="two")
    self_package = write_package(tmp_path / "src" / "self", name="self")
    _add_dependencies(one, "<depend>two</depend>")
    _add_dependencies(two, "<depend>one</depend>")
    _add_dependencies(self_package, "<depend>self</depend>")

    result = analyze_dependencies(ServerSettings(root_path=tmp_path))

    assert result.cycles == [["one", "two"], ["self"]]
    assert sum(issue.code == "DEPENDENCY_CYCLE" for issue in result.issues) == 2


def test_package_scope_includes_reachable_dependencies(
    tmp_path: Path, write_package: Callable[..., Path]
) -> None:
    base = write_package(tmp_path / "src" / "base", name="base")
    app = write_package(tmp_path / "src" / "app", name="app")
    write_package(tmp_path / "src" / "unrelated", name="unrelated")
    _add_dependencies(app, "<depend>base</depend><test_depend>pytest</test_depend>")

    result = analyze_dependencies(ServerSettings(root_path=tmp_path), package_name="app")

    assert result.scope == "package"
    assert result.selected_package == "app"
    assert [package.package_name for package in result.packages] == ["app", "base"]
    assert result.external_dependencies == ["pytest"]
    assert base.exists()


def test_duplicate_names_and_invalid_manifests_are_issues(
    tmp_path: Path, write_package: Callable[..., Path]
) -> None:
    write_package(tmp_path / "src" / "one", name="duplicate")
    write_package(tmp_path / "src" / "two", name="duplicate")
    broken = tmp_path / "src" / "broken"
    broken.mkdir()
    (broken / "package.xml").write_text("<package>", encoding="utf-8")

    result = analyze_dependencies(ServerSettings(root_path=tmp_path))

    codes = {issue.code for issue in result.issues}
    assert "DUPLICATE_PACKAGE_NAME" in codes
    assert "INVALID_PACKAGE_XML" in codes


def test_both_package_selectors_are_rejected(tmp_path: Path) -> None:
    result = analyze_dependencies(
        ServerSettings(root_path=tmp_path),
        package_name="demo",
        relative_path="src/demo",
    )

    assert result.issues[0].code == "INVALID_PACKAGE_SELECTOR"
