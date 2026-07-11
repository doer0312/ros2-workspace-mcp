import asyncio
import sys
from collections.abc import Callable
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

EXPECTED_TOOLS = [
    "scan_workspace",
    "inspect_package",
    "analyze_dependencies",
    "inspect_interfaces",
    "analyze_launch_file",
    "inspect_robot_description",
    "diagnose_workspace",
]


def _snapshot(root: Path) -> dict[str, tuple[int, bytes]]:
    return {
        path.relative_to(root).as_posix(): (path.stat().st_mtime_ns, path.read_bytes())
        for path in root.rglob("*")
        if path.is_file()
    }


def test_real_stdio_calls_all_seven_tools_without_execution_or_writes(
    tmp_path: Path, write_package: Callable[..., Path]
) -> None:
    interfaces = write_package(
        tmp_path / "src" / "demo_interfaces",
        name="demo_interfaces",
        build_type="ament_cmake",
    )
    python_package = write_package(
        tmp_path / "src" / "demo_python",
        name="demo_python",
        build_type="ament_python",
    )
    robot = write_package(
        tmp_path / "src" / "demo_robot",
        name="demo_robot",
        build_type="ament_cmake",
    )
    (interfaces / "CMakeLists.txt").touch()
    message = interfaces / "msg" / "State.msg"
    message.parent.mkdir()
    message.write_text("int32 state\n", encoding="utf-8")
    execution_marker = tmp_path / "WORKSPACE_CODE_EXECUTED"
    (python_package / "setup.py").write_text(
        "from pathlib import Path\n"
        f"Path({str(execution_marker)!r}).write_text('executed')\n"
        "from setuptools import setup\nsetup()\n",
        encoding="utf-8",
    )
    launch = python_package / "launch" / "demo.launch.py"
    launch.parent.mkdir()
    launch.write_text(
        "ExecuteProcess(cmd=['must-not-run', 'WORKSPACE_CODE_EXECUTED'])\n"
        "Node(package='demo_python', executable='demo')\n",
        encoding="utf-8",
    )
    (robot / "CMakeLists.txt").touch()
    urdf = robot / "urdf" / "robot.urdf"
    urdf.parent.mkdir()
    urdf.write_text('<robot name="demo"><link name="base"/></robot>', encoding="utf-8")
    before = _snapshot(tmp_path)

    calls = [
        ("scan_workspace", {}),
        ("inspect_package", {"package_name": "demo_python"}),
        ("analyze_dependencies", {}),
        ("inspect_interfaces", {"package_name": "demo_interfaces"}),
        ("analyze_launch_file", {"relative_path": "src/demo_python/launch/demo.launch.py"}),
        ("inspect_robot_description", {"relative_path": "src/demo_robot/urdf/robot.urdf"}),
        ("diagnose_workspace", {}),
    ]

    async def exercise() -> None:
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
            assert [tool.name for tool in tools.tools] == EXPECTED_TOOLS
            for name, arguments in calls:
                result = await session.call_tool(name, arguments=arguments)
                assert not result.isError
                assert isinstance(result.structuredContent, dict)

    asyncio.run(exercise())

    assert not execution_marker.exists()
    assert _snapshot(tmp_path) == before
