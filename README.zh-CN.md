# ROS 2 Workspace Inspector MCP

[![License: Apache-2.0](https://img.shields.io/badge/License-Apache--2.0-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](pyproject.toml)
[![CI](https://github.com/doer0312/ros2-workspace-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/doer0312/ros2-workspace-mcp/actions/workflows/ci.yml)

[English](README.md) | [简体中文](README.zh-CN.md)

这是一个本地优先、只读、静态分析的 MCP Server，为 Codex、Claude Code、Cursor 等 MCP 客户端提供
结构化的 ROS 2 工作空间信息。七个静态分析工具已全部实现，覆盖工作空间发现、包结构、依赖、
接口、Launch、机器人描述和限流诊断，并且不要求安装 ROS 2。此外还提供两个紧凑只读 Resource
形态和一个引导式审查 Prompt。

```text
7 analysis tools · 2 read-only resource forms · 1 guided review prompt
```

本项目只检查文件，不控制机器人，不运行 ROS 节点，不构建工作空间，不执行 Launch、Xacro、
`setup.py`、工作空间 Python 或 Shell 命令，也不修改用户文件。所有访问均限制在配置 root 内。

## 环境与安装

- Python 3.10 及以上
- [`uv`](https://docs.astral.sh/uv/)

进入仓库并安装锁定的依赖：

```bash
git clone https://github.com/doer0312/ros2-workspace-mcp.git
cd ros2-workspace-mcp
uv sync --locked
```

启动命令：

```bash
uv run ros2-workspace-mcp --root /absolute/path/to/your/ros2_ws
```

等价的模块入口：

```bash
uv run python -m ros2_workspace_mcp --root /absolute/path/to/your/ros2_ws
```

stdout 专用于 MCP 协议消息。参数错误会写入 stderr，并返回非零退出码。

无需安装 ROS 即可使用仓库内的静态示例：

```bash
uv run ros2-workspace-mcp --root ./examples/demo_ws
```

最小请求：

```text
Scan the configured ROS 2 workspace and summarize its packages.
```

Prompt 示例：

```text
Use review_ros2_workspace with depth="standard".
```

## 客户端配置

Codex TOML：

```toml
[mcp_servers.ros2-workspace-inspector]
command = "uv"
args = ["--directory", "/absolute/path/to/ros2-workspace-mcp", "run", "ros2-workspace-mcp", "--root", "/absolute/path/to/your/ros2_ws"]
```

Claude Desktop JSON：

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

可复制的完整示例位于 `examples/client-configs/`。这些配置从本地仓库环境启动，不假设项目已经
发布到 PyPI。

## 已实现工具

Server 恰好提供以下七个工具：

1. `scan_workspace`：发现软件包和基础元数据；
2. `inspect_package`：检查单个包的清单、构建文件、可执行项和文件布局；
3. `analyze_dependencies`：解析依赖声明并建立工作空间依赖图；
4. `inspect_interfaces`：解析单个包的 `.msg`、`.srv` 和 `.action`；
5. `analyze_launch_file`：静态分析单个 Python、XML 或 YAML Launch；
6. `inspect_robot_description`：校验 URDF 或汇总未展开的 Xacro；
7. `diagnose_workspace`：执行限流、去重的工作空间综合诊断。

可以要求 MCP 客户端：`Use scan_workspace to inspect the configured ROS 2 workspace.`

`scan_workspace` 不接收参数，只扫描通过 `--root` 配置的工作空间。压缩后的返回示例：

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

完整结构包括 Server 标识、规范化根目录和扫描目录、软件包元数据、有效/无效计数、重复名称及
结构化问题。详见 [`docs/tools.md`](docs/tools.md)。

## Resources 与 Prompt

- `ros2-workspace://summary`：固定的紧凑工作空间概览；
- `ros2-workspace://package/{package_name}`：严格校验包名并拒绝歧义的包上下文模板；
- `review_ros2_workspace(focus="", depth="standard")`：生成 quick、standard 或 deep 审查说明。

Resource 仅在读取时生成，MIME 类型为 `application/json`，不返回任何原始项目文件。项目明确
不提供任意文件 Resource、订阅、通知或文件监视。不同 MCP 客户端可能以不同方式显示 Resource
和 Prompt。详见 [`docs/resources.md`](docs/resources.md) 与 [`docs/prompts.md`](docs/prompts.md)。

## 安全边界

Server 绑定到一个经过校验和规范化的工作空间目录。每个待读文件都经过规范路径和目录包含关系
校验，不使用字符串前缀判断。扫描不会进入目录符号链接；文件符号链接只有在目标仍位于根目录内
时才允许读取。文本读取统一采用 UTF-8 和大小限制；Python 仅使用 AST，XML 使用
`ElementTree`，YAML 使用 `safe_load`。setup、Launch、Xacro、CMake 和进程声明均不会执行。
完整说明见 [`docs/security.md`](docs/security.md)。

## 开发检查

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

更多文档：

- [Tools](docs/tools.md)
- [Resources](docs/resources.md)
- [Prompts](docs/prompts.md)
- [Architecture](docs/architecture.md)
- [Security boundary](docs/security.md)

## 许可证

本项目采用 Apache License 2.0，详见 `LICENSE`。
