"""MCP boundary for single launch-file analysis."""

from typing import Any

from mcp.server.fastmcp import FastMCP

from ros2_workspace_mcp.analyzers.launch import analyze_launch_file
from ros2_workspace_mcp.config import ServerSettings


def analyze_launch_file_result(
    settings: ServerSettings,
    *,
    relative_path: str,
) -> dict[str, Any]:
    """Return JSON-safe static launch analysis."""
    return analyze_launch_file(settings, relative_path=relative_path).model_dump(mode="json")


def register_launch_tools(server: FastMCP, settings: ServerSettings) -> None:
    """Register single launch-file analysis on a new server."""

    @server.tool(
        name="analyze_launch_file",
        description=(
            "Statically analyze one workspace-relative Python, XML, or YAML ROS 2 launch file. "
            "Returns declared nodes, includes, arguments, environment changes, and processes; "
            "Python uses AST and YAML uses safe loading. It never executes launch actions or "
            "commands."
        ),
        structured_output=True,
    )
    def analyze_launch_file_tool(relative_path: str) -> dict[str, Any]:
        return analyze_launch_file_result(settings, relative_path=relative_path)
