from pathlib import Path

from ros2_workspace_mcp.analyzers.robot import inspect_robot_description
from ros2_workspace_mcp.config import ServerSettings


def test_path_escape_and_unsupported_format(tmp_path: Path) -> None:
    settings = ServerSettings(root_path=tmp_path)

    escaped = inspect_robot_description(settings, relative_path="../robot.urdf")
    unsupported = inspect_robot_description(settings, relative_path="robot.xml")

    assert escaped.issues[0].code == "PATH_OUTSIDE_ROOT"
    assert unsupported.issues[0].code == "UNSUPPORTED_ROBOT_DESCRIPTION_FORMAT"


def test_xacro_include_and_direct_cycle(tmp_path: Path) -> None:
    first = tmp_path / "first.xacro"
    second = tmp_path / "second.xacro"
    first.write_text(
        '<robot xmlns:xacro="http://www.ros.org/wiki/xacro">'
        '<xacro:include filename="second.xacro"/></robot>',
        encoding="utf-8",
    )
    second.write_text(
        '<robot xmlns:xacro="http://www.ros.org/wiki/xacro">'
        '<xacro:include filename="first.xacro"/></robot>',
        encoding="utf-8",
    )

    result = inspect_robot_description(
        ServerSettings(root_path=tmp_path), relative_path="first.xacro"
    )

    assert result.xacro_summary is not None
    assert result.xacro_summary.includes[0].resolvable
    assert result.xacro_summary.include_cycles == [["first.xacro", "second.xacro"]]
    assert any(issue.code == "XACRO_INCLUDE_CYCLE" for issue in result.issues)


def test_xacro_dynamic_include_is_not_opened(tmp_path: Path) -> None:
    path = tmp_path / "dynamic.xacro"
    path.write_text(
        '<robot xmlns:xacro="http://www.ros.org/wiki/xacro">'
        '<xacro:include filename="$(find-pkg-share demo)/part.xacro"/></robot>',
        encoding="utf-8",
    )

    result = inspect_robot_description(ServerSettings(root_path=tmp_path), relative_path=path.name)

    assert result.xacro_summary is not None
    assert result.xacro_summary.includes[0].dynamic
    assert not result.xacro_summary.includes[0].resolvable
