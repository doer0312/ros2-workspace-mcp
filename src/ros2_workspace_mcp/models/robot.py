"""Models for static URDF and Xacro inspection."""

from typing import Any

from pydantic import BaseModel, Field

from ros2_workspace_mcp.models.common import ScanIssue


class RobotGeometry(BaseModel):
    """A visual or collision geometry summary."""

    kind: str
    dimensions: dict[str, Any] = Field(default_factory=dict)
    mesh_filename: str | None = None


class RobotLink(BaseModel):
    """A URDF link summary."""

    name: str
    visuals: list[RobotGeometry] = Field(default_factory=list)
    collisions: list[RobotGeometry] = Field(default_factory=list)
    inertial: dict[str, Any] | None = None


class RobotJoint(BaseModel):
    """A URDF joint and kinematic relation."""

    name: str
    type: str | None = None
    parent: str | None = None
    child: str | None = None
    origin: dict[str, str] = Field(default_factory=dict)
    axis: str | None = None
    limits: dict[str, float] = Field(default_factory=dict)
    dynamics: dict[str, float] = Field(default_factory=dict)
    safety_controller: dict[str, float] = Field(default_factory=dict)
    calibration: dict[str, float] = Field(default_factory=dict)
    mimic: dict[str, Any] | None = None


class MeshReference(BaseModel):
    """A mesh URI with conservative resolution status."""

    filename: str
    package_uri: bool
    resolvable: bool | None = None


class XacroInclude(BaseModel):
    """A static or dynamic Xacro include declaration."""

    filename: str | None = None
    dynamic: bool = False
    resolvable: bool = False


class XacroSummary(BaseModel):
    """Unexpanded Xacro declarations."""

    properties: list[str] = Field(default_factory=list)
    macros: list[str] = Field(default_factory=list)
    arguments: list[str] = Field(default_factory=list)
    includes: list[XacroInclude] = Field(default_factory=list)
    macro_calls: list[str] = Field(default_factory=list)
    dynamic_expressions: list[str] = Field(default_factory=list)
    include_cycles: list[list[str]] = Field(default_factory=list)
    contains_dynamic_expressions: bool = False


class RobotDescriptionInspectionResult(BaseModel):
    """Static URDF or unexpanded Xacro inspection result."""

    relative_path: str | None
    format: str | None
    robot_name: str | None = None
    valid: bool
    expanded: bool
    links: list[RobotLink] = Field(default_factory=list)
    joints: list[RobotJoint] = Field(default_factory=list)
    root_links: list[str] = Field(default_factory=list)
    leaf_links: list[str] = Field(default_factory=list)
    transmissions: list[str] = Field(default_factory=list)
    has_gazebo_extensions: bool = False
    mesh_references: list[MeshReference] = Field(default_factory=list)
    xacro_summary: XacroSummary | None = None
    issues: list[ScanIssue] = Field(default_factory=list)
