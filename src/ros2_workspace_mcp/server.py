"""MCP server construction and stdio execution."""

from mcp.server.fastmcp import FastMCP

from ros2_workspace_mcp.config import ServerSettings
from ros2_workspace_mcp.prompts.review import register_review_prompt
from ros2_workspace_mcp.resources.package import register_package_resource
from ros2_workspace_mcp.resources.workspace import register_workspace_resource
from ros2_workspace_mcp.tools.dependencies import register_dependency_tools
from ros2_workspace_mcp.tools.diagnosis import register_diagnosis_tools
from ros2_workspace_mcp.tools.interfaces import register_interface_tools
from ros2_workspace_mcp.tools.launch import register_launch_tools
from ros2_workspace_mcp.tools.package import register_package_tools
from ros2_workspace_mcp.tools.robot import register_robot_tools
from ros2_workspace_mcp.tools.workspace import register_workspace_tools


def create_server(settings: ServerSettings) -> FastMCP:
    """Create an unstarted MCP server for the configured workspace."""
    server = FastMCP(
        name=settings.server_name,
        instructions=(
            "Local, read-only ROS 2 workspace inspection server. "
            f"Workspace root: {settings.root_path}"
        ),
    )
    register_workspace_tools(server, settings)
    register_package_tools(server, settings)
    register_dependency_tools(server, settings)
    register_interface_tools(server, settings)
    register_launch_tools(server, settings)
    register_robot_tools(server, settings)
    register_diagnosis_tools(server, settings)
    register_workspace_resource(server, settings)
    register_package_resource(server, settings)
    register_review_prompt(server)
    return server


def run_server(settings: ServerSettings) -> None:
    """Create and run the server using the stdio transport."""
    server = create_server(settings)
    server.run(transport="stdio")
