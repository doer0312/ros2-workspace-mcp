import asyncio
import json
import sys
from collections.abc import Callable
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from pydantic import AnyUrl

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


def test_stdio_resources_prompts_and_existing_tool(
    tmp_path: Path, write_package: Callable[..., Path]
) -> None:
    package = write_package(tmp_path / "src" / "demo", name="demo", build_type="ament_python")
    marker = tmp_path / "SETUP_EXECUTED"
    (package / "setup.py").write_text(
        f"from pathlib import Path\nPath({str(marker)!r}).write_text('bad')\n",
        encoding="utf-8",
    )
    before = _snapshot(tmp_path)

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
            resources = await session.list_resources()
            templates = await session.list_resource_templates()
            prompts = await session.list_prompts()
            assert [tool.name for tool in tools.tools] == EXPECTED_TOOLS
            assert [str(resource.uri) for resource in resources.resources] == [
                "ros2-workspace://summary"
            ]
            assert [template.uriTemplate for template in templates.resourceTemplates] == [
                "ros2-workspace://package/{package_name}"
            ]
            assert [prompt.name for prompt in prompts.prompts] == ["review_ros2_workspace"]

            summary = await session.read_resource(AnyUrl("ros2-workspace://summary"))
            context = await session.read_resource(AnyUrl("ros2-workspace://package/demo"))
            summary_payload = json.loads(summary.contents[0].text)
            package_payload = json.loads(context.contents[0].text)
            assert summary.contents[0].mimeType == "application/json"
            assert context.contents[0].mimeType == "application/json"
            assert summary_payload["package_count"] == 1
            assert package_payload["name"] == "demo"

            for depth in ("quick", "standard", "deep"):
                prompt = await session.get_prompt(
                    "review_ros2_workspace",
                    {"focus": "dependency cycles", "depth": depth},
                )
                assert prompt.messages[0].role == "user"
                assert f"Review depth: {depth}" in prompt.messages[0].content.text

            tool_result = await session.call_tool("scan_workspace", arguments={})
            assert not tool_result.isError
            assert tool_result.structuredContent["package_count"] == 1

    asyncio.run(exercise())

    assert not marker.exists()
    assert _snapshot(tmp_path) == before
