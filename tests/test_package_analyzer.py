import json
from collections.abc import Callable
from pathlib import Path

from ros2_workspace_mcp.analyzers.package import inspect_package
from ros2_workspace_mcp.config import ServerSettings


def test_inspects_python_package_without_executing_setup(
    tmp_path: Path, write_package: Callable[..., Path]
) -> None:
    package = write_package(tmp_path / "src" / "demo", name="demo", build_type="ament_python")
    (package / "setup.py").write_text(
        "from setuptools import setup\n"
        "setup(entry_points={'console_scripts': ['demo = demo.main:main']})\n"
        "raise RuntimeError('must never execute')\n",
        encoding="utf-8",
    )
    (package / "launch").mkdir()
    (package / "launch" / "demo.launch.py").touch()
    (package / "config").mkdir()
    (package / "config" / "demo.yaml").touch()

    result = inspect_package(ServerSettings(root_path=tmp_path), package_name="demo")

    assert result.valid
    assert result.build_system is not None
    assert result.build_system.inferred_build_type == "ament_python"
    assert [entry.name for entry in result.executables] == ["demo"]
    assert result.launch_files == ["src/demo/launch/demo.launch.py"]
    assert result.config_files == ["src/demo/config/demo.yaml"]


def test_inspects_cmake_package_and_classifies_files(
    tmp_path: Path, write_package: Callable[..., Path]
) -> None:
    package = write_package(tmp_path / "src" / "robot", name="robot", build_type="ament_cmake")
    (package / "CMakeLists.txt").write_text(
        "add_executable(node src/node.cpp)\ninstall(TARGETS node DESTINATION lib)\n",
        encoding="utf-8",
    )
    for relative in (
        "launch/robot.launch.xml",
        "msg/State.msg",
        "srv/Reset.srv",
        "action/Move.action",
        "urdf/robot.urdf",
        "description/part.xacro",
        "test/test_robot.py",
        "resource/robot",
        "rviz/view.rviz",
        "meshes/body.stl",
    ):
        path = package / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()

    result = inspect_package(ServerSettings(root_path=tmp_path), relative_path="src/robot")

    assert [entry.name for entry in result.executables] == ["node"]
    assert len(result.interface_files) == 3
    assert len(result.robot_description_files) == 2
    assert len(result.resource_files) == 3
    assert result.test_files == ["src/robot/test/test_robot.py"]
    json.dumps(result.model_dump(mode="json"))


def test_invalid_package_xml_is_partial_result(tmp_path: Path) -> None:
    package = tmp_path / "broken"
    package.mkdir()
    (package / "package.xml").write_text("<package>", encoding="utf-8")

    result = inspect_package(ServerSettings(root_path=tmp_path), relative_path="broken")

    assert not result.valid
    assert result.manifest is None
    assert any(issue.code == "INVALID_PACKAGE_XML" for issue in result.issues)


def test_missing_package_name_returns_error(tmp_path: Path) -> None:
    result = inspect_package(ServerSettings(root_path=tmp_path), package_name="missing")

    assert not result.valid
    assert result.issues[0].code == "PACKAGE_NOT_FOUND"


def test_duplicate_package_name_requires_relative_path(
    tmp_path: Path, write_package: Callable[..., Path]
) -> None:
    write_package(tmp_path / "src" / "one", name="duplicate")
    write_package(tmp_path / "src" / "two", name="duplicate")

    ambiguous = inspect_package(ServerSettings(root_path=tmp_path), package_name="duplicate")
    selected = inspect_package(ServerSettings(root_path=tmp_path), relative_path="src/two")

    assert ambiguous.issues[0].code == "AMBIGUOUS_PACKAGE_NAME"
    assert ambiguous.selection_candidates == ["src/one", "src/two"]
    assert selected.relative_path == "src/two"


def test_package_path_escape_is_rejected(tmp_path: Path) -> None:
    result = inspect_package(ServerSettings(root_path=tmp_path), relative_path="../outside")

    assert not result.valid
    assert result.issues[0].code == "PATH_OUTSIDE_ROOT"


def test_dynamic_setup_expression_is_reported(
    tmp_path: Path, write_package: Callable[..., Path]
) -> None:
    package = write_package(tmp_path / "demo", name="demo")
    (package / "setup.py").write_text(
        "from setuptools import setup\nscripts = []\n"
        "setup(entry_points={'console_scripts': scripts})\n",
        encoding="utf-8",
    )

    result = inspect_package(ServerSettings(root_path=tmp_path), package_name="demo")

    assert any(issue.code == "DYNAMIC_BUILD_EXPRESSION" for issue in result.issues)


def test_file_lists_are_stably_sorted(tmp_path: Path, write_package: Callable[..., Path]) -> None:
    package = write_package(tmp_path / "demo", name="demo")
    launch = package / "launch"
    launch.mkdir()
    (launch / "z.launch.py").touch()
    (launch / "a.launch.xml").touch()

    result = inspect_package(ServerSettings(root_path=tmp_path), package_name="demo")

    assert result.launch_files == ["demo/launch/a.launch.xml", "demo/launch/z.launch.py"]
