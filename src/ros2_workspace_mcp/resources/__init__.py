"""Read-only MCP resource registration."""

from ros2_workspace_mcp.resources.package import register_package_resource
from ros2_workspace_mcp.resources.workspace import register_workspace_resource

__all__ = ["register_package_resource", "register_workspace_resource"]
