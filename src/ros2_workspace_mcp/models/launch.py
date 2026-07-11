"""Models for static ROS 2 launch-file analysis."""

from typing import Any

from pydantic import BaseModel, Field

from ros2_workspace_mcp.models.common import ScanIssue


class LaunchNode(BaseModel):
    """A statically declared launch node."""

    package: str | None = None
    executable: str | None = None
    name: str | None = None
    namespace: str | None = None
    parameters: list[Any] = Field(default_factory=list)
    remappings: list[Any] = Field(default_factory=list)
    arguments: list[Any] = Field(default_factory=list)
    condition: str | None = None
    dynamic: bool = False


class LaunchArgument(BaseModel):
    """A declared launch argument."""

    name: str | None = None
    default: Any = None
    description: str | None = None
    dynamic: bool = False


class LaunchInclude(BaseModel):
    """A non-recursively inspected launch include."""

    path: str | None = None
    resolvable: bool = False
    dynamic: bool = False
    condition: str | None = None


class LaunchEnvironmentChange(BaseModel):
    """A statically declared environment change."""

    name: str | None = None
    value: Any = None
    dynamic: bool = False


class LaunchProcess(BaseModel):
    """An ExecuteProcess/executable declaration that is never run."""

    command: Any = None
    condition: str | None = None
    dynamic: bool = False


class LaunchAnalysisResult(BaseModel):
    """Static analysis result for one launch file."""

    relative_path: str | None
    format: str | None
    valid: bool
    nodes: list[LaunchNode] = Field(default_factory=list)
    includes: list[LaunchInclude] = Field(default_factory=list)
    arguments: list[LaunchArgument] = Field(default_factory=list)
    environment_changes: list[LaunchEnvironmentChange] = Field(default_factory=list)
    processes: list[LaunchProcess] = Field(default_factory=list)
    entities: list[str] = Field(default_factory=list)
    dynamic_expressions: list[str] = Field(default_factory=list)
    issues: list[ScanIssue] = Field(default_factory=list)
