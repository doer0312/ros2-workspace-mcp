# ROS 2 Workspace Inspector MCP

[![License: Apache-2.0](https://img.shields.io/badge/License-Apache--2.0-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](pyproject.toml)
[![CI](https://github.com/doer0312/ros2-workspace-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/doer0312/ros2-workspace-mcp/actions/workflows/ci.yml)

[English](README.md) | [简体中文](README.zh-CN.md)

ROS 2 Workspace Inspector MCP is a local-first, read-only static-analysis MCP server that gives Codex, Claude Code,
Cursor, and other MCP clients structured information about ROS 2 workspaces. Seven static-analysis
tools cover discovery, package structure, dependencies, interfaces, launch files, robot
descriptions, and bounded workspace diagnosis without requiring ROS 2. It also provides two
compact read-only resources and one guided review prompt.

```text
7 analysis tools · 2 read-only resource forms · 1 guided review prompt
```

The project inspects files only. It does not control robots, run ROS nodes, build workspaces,
execute launch or Xacro files, execute `setup.py`, publish topics, call services or actions, or
modify user files. All access stays inside the configured root sandbox. Only stdio is supported.

## Tools

- `scan_workspace` — Discover ROS 2 packages, workspace layout, build types, and basic manifest metadata.
- `inspect_package` — Inspect a package's manifest, build configuration, executables, launch files, interfaces, robot descriptions, and tests.
- `analyze_dependencies` — Analyze package dependencies, internal dependency edges, topological order, and dependency cycles.
- `inspect_interfaces` — Parse and inspect ROS 2 Msg, Srv, and Action interface definitions.
- `analyze_launch_file` — Statically analyze a Python, XML, or YAML ROS 2 launch file without executing it.
- `inspect_robot_description` — Inspect URDF structure and statically summarize Xacro files without expanding or executing them.
- `diagnose_workspace` — Run a consolidated, bounded diagnosis of the configured ROS 2 workspace.

## Requirements and installation

- Python 3.10 or newer
- [`uv`](https://docs.astral.sh/uv/)

Clone the repository, enter it, and create the locked environment:

```bash
git clone https://github.com/doer0312/ros2-workspace-mcp.git
cd ros2-workspace-mcp
uv sync --locked
```

Run against a local workspace:

```bash
uv run ros2-workspace-mcp --root /absolute/path/to/your/ros2_ws
```

The equivalent module entry point is:

```bash
uv run python -m ros2_workspace_mcp --root /absolute/path/to/your/ros2_ws
```

The process communicates via stdout using the MCP protocol. Do not redirect ordinary logs to
stdout. Invalid CLI input is reported on stderr with a non-zero exit status.

## Client configuration

Codex TOML:

```toml
[mcp_servers.ros2-workspace-inspector]
command = "uv"
args = ["--directory", "/absolute/path/to/ros2-workspace-mcp", "run", "ros2-workspace-mcp", "--root", "/absolute/path/to/your/ros2_ws"]
```

Claude Desktop JSON:

```json
{
  "mcpServers": {
    "ros2-workspace-inspector": {
      "command": "uv",
      "args": ["--directory", "/absolute/path/to/ros2-workspace-mcp", "run", "ros2-workspace-mcp", "--root", "/absolute/path/to/your/ros2_ws"]
    }
  }
}
```

Copyable versions are available under `examples/client-configs/`. Both examples run the checked-out
repository environment and do not assume a PyPI release.

Try the included static demo without installing ROS:

```bash
uv run ros2-workspace-mcp --root ./examples/demo_ws
```

Minimal request:

```text
Scan the configured ROS 2 workspace and summarize its packages.
```

Guided review example:

```text
Use review_ros2_workspace with depth="standard".
```

## Available tools

The server exposes exactly seven tools:

1. `scan_workspace` — discover packages and basic metadata.
2. `inspect_package` — inspect one package's manifest, build files, executables, and file layout.
3. `analyze_dependencies` — parse declarations and build a workspace dependency graph.
4. `inspect_interfaces` — parse one package's `.msg`, `.srv`, and `.action` files.
5. `analyze_launch_file` — statically analyze one Python, XML, or YAML launch file.
6. `inspect_robot_description` — validate URDF or summarize unexpanded Xacro.
7. `diagnose_workspace` — run a bounded, deduplicated workspace-wide diagnosis.

Example requests:

```text
Use scan_workspace to inspect the configured ROS 2 workspace.
Inspect the package named demo_robot.
Analyze src/demo_robot/launch/demo.launch.py without running it.
Diagnose the configured workspace.
```

`scan_workspace` takes no arguments and scans only the workspace supplied with `--root`. A compact
result looks like this:

```json
{
  "layout": "colcon_workspace",
  "package_count": 1,
  "packages": [
    {
      "name": "demo_pkg",
      "relative_path": "src/demo_pkg",
      "build_type": "ament_python",
      "build_type_source": "inferred",
      "valid": true
    }
  ],
  "issues": []
}
```

The full result also includes server identity, canonical root and scan paths, package metadata,
valid/invalid counts, duplicate names, and structured issues. See [`docs/tools.md`](docs/tools.md).

## Resources and prompt

- `ros2-workspace://summary` is a fixed compact workspace summary.
- `ros2-workspace://package/{package_name}` is a package context template with strict name
  validation and ambiguity errors.
- `review_ros2_workspace(focus="", depth="standard")` guides quick, standard, or deep review using
  the seven tools without reading the workspace while the prompt is generated.

Resources are generated on read, have `application/json` MIME type, and never return raw project
files. The server intentionally does not expose an arbitrary file resource, subscriptions,
notifications, or filesystem watching. Client applications may display resources and prompts in
different ways. See [`docs/resources.md`](docs/resources.md) and
[`docs/prompts.md`](docs/prompts.md).

## Security boundary

The server is bound to one validated, canonical workspace directory. Every file selected for
reading is resolved and checked with path containment rather than string prefixes. Directory
symlinks are never traversed; readable file symlinks must resolve inside the root. Text reads are
UTF-8, size-limited, and centralized. Python is parsed with AST, XML with `ElementTree`, and YAML
with `safe_load`; setup, launch, Xacro, CMake, and process declarations are never executed. See
[`docs/security.md`](docs/security.md) for the complete boundary.

## Development

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

Further documentation:

- [Tools](docs/tools.md)
- [Resources](docs/resources.md)
- [Prompts](docs/prompts.md)
- [Architecture](docs/architecture.md)
- [Security boundary](docs/security.md)

## License

Licensed under the Apache License 2.0. See `LICENSE`.
