"""MCP boundary for dependency graph analysis."""

from typing import Any

from mcp.server.fastmcp import FastMCP

from ros2_workspace_mcp.analyzers.dependencies import analyze_dependencies
from ros2_workspace_mcp.config import ServerSettings


def analyze_dependencies_result(
    settings: ServerSettings,
    *,
    package_name: str | None = None,
    relative_path: str | None = None,
) -> dict[str, Any]:
    """Return JSON-safe workspace or package dependency analysis."""
    return analyze_dependencies(
        settings,
        package_name=package_name,
        relative_path=relative_path,
    ).model_dump(mode="json")


def register_dependency_tools(server: FastMCP, settings: ServerSettings) -> None:
    """Register dependency analysis on a new server."""

    @server.tool(
        name="analyze_dependencies",
        description=(
            "Parse package.xml dependency declarations and build a deterministic workspace graph. "
            "With no selector it analyzes the workspace; with package_name or relative_path it "
            "analyzes that package scope. It does not run rosdep, query the network, or install "
            "anything."
        ),
        structured_output=True,
    )
    def analyze_dependencies_tool(
        package_name: str | None = None,
        relative_path: str | None = None,
    ) -> dict[str, Any]:
        return analyze_dependencies_result(
            settings,
            package_name=package_name,
            relative_path=relative_path,
        )
