"""MCP boundary for bounded workspace diagnosis."""

from typing import Any

from mcp.server.fastmcp import FastMCP

from ros2_workspace_mcp.analyzers.diagnosis import diagnose_workspace
from ros2_workspace_mcp.config import ServerSettings


def diagnose_workspace_result(settings: ServerSettings) -> dict[str, Any]:
    """Return a compact JSON-safe workspace diagnosis."""
    return diagnose_workspace(settings).model_dump(mode="json")


def register_diagnosis_tools(server: FastMCP, settings: ServerSettings) -> None:
    """Register bounded workspace diagnosis on a new server."""

    @server.tool(
        name="diagnose_workspace",
        description=(
            "Run a bounded, read-only diagnosis of the configured workspace by reusing package, "
            "dependency, interface, launch, and robot-description analyzers. Returns compact "
            "severity summaries and deduplicated issues; it does not build, execute, or modify "
            "files."
        ),
        structured_output=True,
    )
    def diagnose_workspace_tool() -> dict[str, Any]:
        return diagnose_workspace_result(settings)
