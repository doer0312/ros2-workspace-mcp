"""MCP boundary for workspace discovery."""

from typing import Any

from mcp.server.fastmcp import FastMCP

from ros2_workspace_mcp.analyzers.workspace import analyze_workspace
from ros2_workspace_mcp.config import ServerSettings


def scan_workspace(settings: ServerSettings) -> dict[str, Any]:
    """Return a JSON-safe scan result for the configured workspace."""
    return analyze_workspace(settings).model_dump(mode="json")


def register_workspace_tools(server: FastMCP, settings: ServerSettings) -> None:
    """Register workspace tools exactly once on one newly created server."""

    @server.tool(
        name="scan_workspace",
        description=(
            "Scan the configured ROS 2 workspace for packages and basic package.xml metadata. "
            "This read-only tool does not build, run, or modify the workspace, and it does not "
            "perform full dependency, launch, interface, or robot-description analysis."
        ),
        structured_output=True,
    )
    def scan_workspace_tool() -> dict[str, Any]:
        return scan_workspace(settings)
