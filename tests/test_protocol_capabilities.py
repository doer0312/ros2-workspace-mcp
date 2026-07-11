import asyncio
import json
from collections.abc import Callable
from pathlib import Path

import pytest

from ros2_workspace_mcp.config import ServerSettings
from ros2_workspace_mcp.server import create_server


def test_public_capability_lists_and_reads(
    tmp_path: Path, write_package: Callable[..., Path]
) -> None:
    write_package(tmp_path / "demo", name="demo")
    server = create_server(ServerSettings(root_path=tmp_path))

    async def inspect() -> None:
        assert len(await server.list_tools()) == 7
        resources = await server.list_resources()
        templates = await server.list_resource_templates()
        prompts = await server.list_prompts()
        assert [str(resource.uri) for resource in resources] == ["ros2-workspace://summary"]
        assert [template.uriTemplate for template in templates] == [
            "ros2-workspace://package/{package_name}"
        ]
        assert [prompt.name for prompt in prompts] == ["review_ros2_workspace"]

        summary = next(iter(await server.read_resource("ros2-workspace://summary")))
        package = next(iter(await server.read_resource("ros2-workspace://package/demo")))
        prompt = await server.get_prompt("review_ros2_workspace", {"depth": "quick"})
        assert json.loads(summary.content)["package_count"] == 1
        assert json.loads(package.content)["name"] == "demo"
        assert prompt.messages[0].role == "user"

    asyncio.run(inspect())


def test_invalid_prompt_depth_is_public_error(tmp_path: Path) -> None:
    server = create_server(ServerSettings(root_path=tmp_path))

    with pytest.raises(ValueError, match="quick, standard, deep"):
        asyncio.run(server.get_prompt("review_ros2_workspace", {"depth": "invalid"}))


def test_server_instances_do_not_share_registrations(tmp_path: Path) -> None:
    first = create_server(ServerSettings(root_path=tmp_path))
    second = create_server(ServerSettings(root_path=tmp_path))

    async def counts(server) -> tuple[int, int, int, int]:
        return (
            len(await server.list_tools()),
            len(await server.list_resources()),
            len(await server.list_resource_templates()),
            len(await server.list_prompts()),
        )

    assert asyncio.run(counts(first)) == (7, 1, 1, 1)
    assert asyncio.run(counts(second)) == (7, 1, 1, 1)
