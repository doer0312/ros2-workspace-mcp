"""MCP boundary for ROS interface inspection."""

from typing import Any

from mcp.server.fastmcp import FastMCP

from ros2_workspace_mcp.analyzers.interfaces import inspect_interfaces
from ros2_workspace_mcp.config import ServerSettings


def inspect_interfaces_result(
    settings: ServerSettings,
    *,
    package_name: str | None = None,
    relative_path: str | None = None,
    interface_name: str | None = None,
) -> dict[str, Any]:
    """Return JSON-safe interface inspection."""
    return inspect_interfaces(
        settings,
        package_name=package_name,
        relative_path=relative_path,
        interface_name=interface_name,
    ).model_dump(mode="json")


def register_interface_tools(server: FastMCP, settings: ServerSettings) -> None:
    """Register ROS interface inspection on a new server."""

    @server.tool(
        name="inspect_interfaces",
        description=(
            "Statically parse .msg, .srv, and .action files in one package selected by name or "
            "relative path, optionally filtering by interface_name. It validates local syntax and "
            "classifies type references without ROS generators, imports, builds, or file changes."
        ),
        structured_output=True,
    )
    def inspect_interfaces_tool(
        package_name: str | None = None,
        relative_path: str | None = None,
        interface_name: str | None = None,
    ) -> dict[str, Any]:
        return inspect_interfaces_result(
            settings,
            package_name=package_name,
            relative_path=relative_path,
            interface_name=interface_name,
        )
