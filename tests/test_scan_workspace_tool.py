import asyncio
import importlib
import sys
from collections.abc import Callable
from pathlib import Path
from unittest.mock import Mock

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from ros2_workspace_mcp.analyzers import workspace as workspace_analyzer
from ros2_workspace_mcp.config import ServerSettings
from ros2_workspace_mcp.server import create_server
from ros2_workspace_mcp.tools import workspace as workspace_tools
from ros2_workspace_mcp.tools.workspace import scan_workspace


def test_server_registers_only_scan_workspace(tmp_path: Path) -> None:
    server = create_server(ServerSettings(root_path=tmp_path))

    tools = asyncio.run(server.list_tools())

    assert [tool.name for tool in tools] == [
        "scan_workspace",
        "inspect_package",
        "analyze_dependencies",
        "inspect_interfaces",
        "analyze_launch_file",
        "inspect_robot_description",
        "diagnose_workspace",
    ]
    assert tools[0].inputSchema == {
        "properties": {},
        "title": "scan_workspace_toolArguments",
        "type": "object",
    }


def test_public_tool_call_returns_structured_result(
    tmp_path: Path, write_package: Callable[..., Path]
) -> None:
    write_package(tmp_path / "demo", name="demo_pkg", build_type="ament_python")
    server = create_server(ServerSettings(root_path=tmp_path))

    content, structured = asyncio.run(server.call_tool("scan_workspace", {}))

    assert content[0].type == "text"
    assert structured["package_count"] == 1
    assert structured["packages"][0]["name"] == "demo_pkg"


def test_tool_function_has_no_root_argument(tmp_path: Path) -> None:
    result = scan_workspace(ServerSettings(root_path=tmp_path))

    assert result["root_path"] == str(tmp_path.resolve())


def test_tool_does_not_modify_workspace(tmp_path: Path, write_package: Callable[..., Path]) -> None:
    write_package(tmp_path / "demo")
    before = {
        path.relative_to(tmp_path): (path.stat().st_mtime_ns, path.read_bytes())
        for path in tmp_path.rglob("*")
        if path.is_file()
    }

    scan_workspace(ServerSettings(root_path=tmp_path))

    after = {
        path.relative_to(tmp_path): (path.stat().st_mtime_ns, path.read_bytes())
        for path in tmp_path.rglob("*")
        if path.is_file()
    }
    assert after == before


def test_importing_tool_module_does_not_scan(monkeypatch) -> None:
    analyze = Mock()
    with monkeypatch.context() as context:
        context.setattr(workspace_analyzer, "analyze_workspace", analyze)

        importlib.reload(workspace_tools)

    analyze.assert_not_called()
    importlib.reload(workspace_tools)


def test_real_stdio_client_lists_and_calls_tool(
    tmp_path: Path, write_package: Callable[..., Path]
) -> None:
    package = write_package(tmp_path / "src" / "demo_pkg", name="demo_pkg")
    (package / "setup.py").touch()

    async def exercise_stdio() -> None:
        parameters = StdioServerParameters(
            command=sys.executable,
            args=["-m", "ros2_workspace_mcp", "--root", str(tmp_path)],
        )
        async with (
            stdio_client(parameters) as (read_stream, write_stream),
            ClientSession(read_stream, write_stream) as session,
        ):
            await session.initialize()
            tools = await session.list_tools()
            assert [tool.name for tool in tools.tools] == [
                "scan_workspace",
                "inspect_package",
                "analyze_dependencies",
                "inspect_interfaces",
                "analyze_launch_file",
                "inspect_robot_description",
                "diagnose_workspace",
            ]

            result = await session.call_tool("scan_workspace", arguments={})
            assert not result.isError
            assert result.structuredContent is not None
            assert result.structuredContent["packages"][0]["name"] == "demo_pkg"

    asyncio.run(exercise_stdio())
