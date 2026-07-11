import asyncio
from collections.abc import Callable
from pathlib import Path

from ros2_workspace_mcp.config import ServerSettings
from ros2_workspace_mcp.server import create_server


def test_interface_tool_is_registered(tmp_path: Path) -> None:
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


def test_interface_tool_returns_structured_result(
    tmp_path: Path, write_package: Callable[..., Path]
) -> None:
    package = write_package(tmp_path / "demo", name="demo")
    message = package / "msg" / "Demo.msg"
    message.parent.mkdir()
    message.write_text("string value\n", encoding="utf-8")
    server = create_server(ServerSettings(root_path=tmp_path))

    _, structured = asyncio.run(server.call_tool("inspect_interfaces", {"package_name": "demo"}))

    assert structured["interfaces"][0]["name"] == "Demo"
