import asyncio
from collections.abc import Callable
from pathlib import Path

from ros2_workspace_mcp.config import ServerSettings
from ros2_workspace_mcp.server import create_server

EXPECTED_TOOLS = [
    "scan_workspace",
    "inspect_package",
    "analyze_dependencies",
    "inspect_interfaces",
    "analyze_launch_file",
    "inspect_robot_description",
    "diagnose_workspace",
]


def test_diagnosis_tool_is_zero_argument_and_seventh(tmp_path: Path) -> None:
    server = create_server(ServerSettings(root_path=tmp_path))

    tools = asyncio.run(server.list_tools())

    assert [tool.name for tool in tools] == EXPECTED_TOOLS
    diagnosis = tools[-1]
    assert diagnosis.inputSchema["properties"] == {}


def test_diagnosis_tool_returns_structured_result(
    tmp_path: Path, write_package: Callable[..., Path]
) -> None:
    package = write_package(tmp_path / "demo", name="demo", build_type="ament_python")
    (package / "setup.py").touch()
    server = create_server(ServerSettings(root_path=tmp_path))

    _, structured = asyncio.run(server.call_tool("diagnose_workspace", {}))

    assert structured["status"] == "ok"
    assert structured["workspace_summary"]["package_count"] == 1
