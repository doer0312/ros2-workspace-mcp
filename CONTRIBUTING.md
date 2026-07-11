# Contributing

Thank you for helping improve ROS 2 Workspace Inspector MCP.

## Development setup

Install Python 3.10 or newer and [uv](https://docs.astral.sh/uv/), then run:

```bash
uv sync --locked
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

Keep changes focused and add temporary-directory tests for new behavior. Pull requests should
describe the user impact, security implications, and checks performed.

## Security principles

Workspace files are untrusted data. Never execute workspace Python, setup files, launch actions,
Xacro, CMake, ROS, colcon, or shell commands. Reuse the root sandbox and bounded text reader for all
file access. Preserve stdio stdout exclusively for MCP protocol messages.

Before opening a pull request, ensure the lockfile is current, all checks pass, and no local paths,
credentials, virtual environments, caches, logs, or user ROS workspaces are included.
