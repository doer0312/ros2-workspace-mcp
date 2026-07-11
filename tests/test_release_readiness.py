from pathlib import Path

from ros2_workspace_mcp.analyzers.interfaces import inspect_interfaces
from ros2_workspace_mcp.analyzers.launch import analyze_launch_file
from ros2_workspace_mcp.analyzers.robot import inspect_robot_description
from ros2_workspace_mcp.analyzers.workspace import analyze_workspace
from ros2_workspace_mcp.config import ServerSettings

ROOT = Path(__file__).resolve().parents[1]


def test_release_metadata_and_readme_commands() -> None:
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert 'name = "ros2-workspace-mcp"' in pyproject
    assert 'version = "0.1.0"' in pyproject
    assert 'requires-python = ">=3.10"' in pyproject
    assert '"mcp>=1.27,<2"' in pyproject
    assert "https://github.com/doer0312/ros2-workspace-mcp" in pyproject
    assert "git clone https://github.com/doer0312/ros2-workspace-mcp.git" in readme
    assert "uv sync --locked" in readme
    assert "uv run ros2-workspace-mcp --root ./examples/demo_ws" in readme


def test_documentation_links_exist() -> None:
    for relative in (
        "README.zh-CN.md",
        "docs/tools.md",
        "docs/resources.md",
        "docs/prompts.md",
        "docs/architecture.md",
        "docs/security.md",
        "CONTRIBUTING.md",
        "SECURITY.md",
        "CHANGELOG.md",
    ):
        assert (ROOT / relative).is_file(), relative


def test_demo_workspace_exercises_static_analyzers() -> None:
    demo_root = ROOT / "examples" / "demo_ws"
    settings = ServerSettings(root_path=demo_root)

    scan = analyze_workspace(settings)
    interfaces = inspect_interfaces(settings, package_name="demo_interfaces")
    launch = analyze_launch_file(
        settings,
        relative_path="src/demo_python/launch/demo.launch.py",
    )
    robot = inspect_robot_description(
        settings,
        relative_path="src/demo_robot/urdf/demo.urdf",
    )

    assert [package.name for package in scan.packages] == [
        "demo_interfaces",
        "demo_python",
        "demo_robot",
    ]
    assert interfaces.interfaces[0].name == "Status"
    assert launch.nodes[0].package == "demo_python"
    assert robot.root_links == ["base_link"]
