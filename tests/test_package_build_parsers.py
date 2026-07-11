from pathlib import Path

from ros2_workspace_mcp.models.package import ExecutableSummary
from ros2_workspace_mcp.parsers.build_files import (
    parse_cmake_executables,
    parse_setup_cfg_executables,
    parse_setup_py_executables,
)


def test_static_setup_py_console_scripts(tmp_path: Path) -> None:
    setup_py = tmp_path / "setup.py"
    setup_py.write_text(
        "from setuptools import setup\n"
        "setup(entry_points={'console_scripts': ['demo = demo.main:main']})\n",
        encoding="utf-8",
    )

    entries, dynamic = parse_setup_py_executables(tmp_path, setup_py)

    assert entries == [ExecutableSummary(name="demo", target="demo.main:main", source="setup.py")]
    assert not dynamic


def test_dynamic_setup_py_is_not_evaluated(tmp_path: Path) -> None:
    setup_py = tmp_path / "setup.py"
    setup_py.write_text(
        "from setuptools import setup\n"
        "scripts = ['demo = demo.main:main']\n"
        "setup(entry_points={'console_scripts': scripts})\n",
        encoding="utf-8",
    )

    entries, dynamic = parse_setup_py_executables(tmp_path, setup_py)

    assert entries == []
    assert dynamic


def test_setup_cfg_console_scripts(tmp_path: Path) -> None:
    setup_cfg = tmp_path / "setup.cfg"
    setup_cfg.write_text(
        "[options.entry_points]\nconsole_scripts =\n  demo = demo.main:main\n",
        encoding="utf-8",
    )

    assert parse_setup_cfg_executables(tmp_path, setup_cfg)[0].name == "demo"


def test_cmake_installed_executable(tmp_path: Path) -> None:
    cmake = tmp_path / "CMakeLists.txt"
    cmake.write_text(
        "add_executable(talker src/talker.cpp)\n"
        "ament_target_dependencies(talker rclcpp)\n"
        "install(TARGETS talker DESTINATION lib/${PROJECT_NAME})\n",
        encoding="utf-8",
    )

    entries, dynamic = parse_cmake_executables(tmp_path, cmake)

    assert [entry.name for entry in entries] == ["talker"]
    assert dynamic
