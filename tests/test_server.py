import asyncio
import importlib
from pathlib import Path
from unittest.mock import Mock

from mcp.server.fastmcp import FastMCP

import ros2_workspace_mcp
from ros2_workspace_mcp.config import ServerSettings
from ros2_workspace_mcp.server import create_server, run_server


def test_server_can_be_created(tmp_path: Path) -> None:
    settings = ServerSettings(root_path=tmp_path)

    server = create_server(settings)

    assert isinstance(server, FastMCP)
    assert server.name == settings.server_name
    assert [tool.name for tool in asyncio.run(server.list_tools())] == [
        "scan_workspace",
        "inspect_package",
        "analyze_dependencies",
        "inspect_interfaces",
        "analyze_launch_file",
        "inspect_robot_description",
        "diagnose_workspace",
    ]


def test_run_server_uses_stdio(monkeypatch, tmp_path: Path) -> None:
    server = Mock(spec=FastMCP)
    monkeypatch.setattr("ros2_workspace_mcp.server.create_server", Mock(return_value=server))

    run_server(ServerSettings(root_path=tmp_path))

    server.run.assert_called_once_with(transport="stdio")


def test_importing_package_does_not_start_server(monkeypatch) -> None:
    run = Mock()
    monkeypatch.setattr("ros2_workspace_mcp.server.run_server", run)

    importlib.reload(ros2_workspace_mcp)

    run.assert_not_called()
