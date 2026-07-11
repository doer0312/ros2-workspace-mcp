import asyncio
from pathlib import Path

from ros2_workspace_mcp.config import ServerSettings
from ros2_workspace_mcp.server import create_server


def test_launch_tool_is_registered(tmp_path: Path) -> None:
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


def test_launch_tool_returns_structured_result(tmp_path: Path) -> None:
    path = tmp_path / "demo.launch.py"
    path.write_text("Node(package='demo', executable='node')", encoding="utf-8")
    server = create_server(ServerSettings(root_path=tmp_path))

    _, structured = asyncio.run(
        server.call_tool("analyze_launch_file", {"relative_path": path.name})
    )

    assert structured["nodes"][0]["package"] == "demo"
