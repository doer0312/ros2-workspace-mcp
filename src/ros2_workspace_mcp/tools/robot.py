"""MCP boundary for URDF and Xacro inspection."""

from typing import Any

from mcp.server.fastmcp import FastMCP

from ros2_workspace_mcp.analyzers.robot import inspect_robot_description
from ros2_workspace_mcp.config import ServerSettings


def inspect_robot_description_result(
    settings: ServerSettings,
    *,
    relative_path: str,
) -> dict[str, Any]:
    """Return JSON-safe URDF or Xacro inspection."""
    return inspect_robot_description(settings, relative_path=relative_path).model_dump(mode="json")


def register_robot_tools(server: FastMCP, settings: ServerSettings) -> None:
    """Register robot-description inspection on a new server."""

    @server.tool(
        name="inspect_robot_description",
        description=(
            "Statically inspect one workspace-relative URDF or Xacro file. URDF returns links, "
            "joints, kinematic validation, and mesh references; Xacro returns an explicitly "
            "unexpanded macro/property/include summary. It never runs xacro or ROS."
        ),
        structured_output=True,
    )
    def inspect_robot_description_tool(relative_path: str) -> dict[str, Any]:
        return inspect_robot_description_result(settings, relative_path=relative_path)
