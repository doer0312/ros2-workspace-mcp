"""MCP boundary for detailed package inspection."""

from typing import Any

from mcp.server.fastmcp import FastMCP

from ros2_workspace_mcp.analyzers.package import inspect_package
from ros2_workspace_mcp.config import ServerSettings


def inspect_package_result(
    settings: ServerSettings,
    *,
    package_name: str | None = None,
    relative_path: str | None = None,
) -> dict[str, Any]:
    """Return one package inspection as JSON-safe data."""
    return inspect_package(
        settings,
        package_name=package_name,
        relative_path=relative_path,
    ).model_dump(mode="json")


def register_package_tools(server: FastMCP, settings: ServerSettings) -> None:
    """Register detailed package inspection on a new server."""

    @server.tool(
        name="inspect_package",
        description=(
            "Statically inspect one package selected by package_name or workspace-relative path. "
            "Returns detailed manifest, build, executable, and file metadata without importing, "
            "building, running, or modifying package code."
        ),
        structured_output=True,
    )
    def inspect_package_tool(
        package_name: str | None = None,
        relative_path: str | None = None,
    ) -> dict[str, Any]:
        return inspect_package_result(
            settings,
            package_name=package_name,
            relative_path=relative_path,
        )
