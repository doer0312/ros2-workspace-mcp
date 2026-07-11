"""Command-line interface for the stdio MCP server."""

import argparse
from collections.abc import Sequence

from pydantic import ValidationError

from ros2_workspace_mcp.config import ServerSettings
from ros2_workspace_mcp.server import run_server


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser without reading process state."""
    parser = argparse.ArgumentParser(
        prog="ros2-workspace-mcp",
        description="Run the read-only ROS 2 Workspace Inspector MCP server over stdio.",
    )
    parser.add_argument("--root", required=True, metavar="PATH", help="ROS 2 workspace root")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Validate CLI input and start the MCP stdio server."""
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        settings = ServerSettings(root_path=args.root)
    except ValidationError as exc:
        first_error = exc.errors(include_url=False)[0]["msg"]
        parser.error(str(first_error).removeprefix("Value error, "))
    run_server(settings)
    return 0
