import asyncio
from collections.abc import Callable
from pathlib import Path

from ros2_workspace_mcp.config import ServerSettings
from ros2_workspace_mcp.server import create_server


def test_dependency_tool_is_registered(tmp_path: Path) -> None:
    server = create_server(ServerSettings(root_path=tmp_path))

    names = [tool.name for tool in asyncio.run(server.list_tools())]

    assert names == [
        "scan_workspace",
        "inspect_package",
        "analyze_dependencies",
        "inspect_interfaces",
        "analyze_launch_file",
        "inspect_robot_description",
        "diagnose_workspace",
    ]


def test_dependency_tool_returns_structured_graph(
    tmp_path: Path, write_package: Callable[..., Path]
) -> None:
    write_package(tmp_path / "demo", name="demo")
    server = create_server(ServerSettings(root_path=tmp_path))

    _, structured = asyncio.run(server.call_tool("analyze_dependencies", {}))

    assert structured["scope"] == "workspace"
    assert structured["topological_order"] == ["demo"]
