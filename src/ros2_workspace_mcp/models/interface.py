"""Models for ROS message, service, and action interface inspection."""

from enum import Enum

from pydantic import BaseModel, Field

from ros2_workspace_mcp.models.common import ScanIssue


class ArrayKind(str, Enum):
    """Supported ROS interface array forms."""

    NONE = "none"
    FIXED = "fixed"
    UNBOUNDED = "unbounded"
    BOUNDED = "bounded"


class InterfaceTypeScope(str, Enum):
    """How an interface field type is resolved."""

    BUILTIN = "builtin_type"
    WORKSPACE = "workspace_type"
    EXTERNAL = "external_type"
    UNRESOLVED_LOCAL = "unresolved_local_type"


class InterfaceField(BaseModel):
    """One parsed interface field."""

    name: str
    raw_type: str
    base_type: str
    package_name: str | None = None
    array_kind: ArrayKind = ArrayKind.NONE
    array_bound: int | None = None
    string_bound: int | None = None
    default_value: str | None = None
    line_number: int
    type_scope: InterfaceTypeScope | None = None


class InterfaceConstant(BaseModel):
    """One parsed interface constant."""

    name: str
    raw_type: str
    value: str
    line_number: int


class InterfaceSection(BaseModel):
    """A msg body or one srv/action section."""

    name: str
    fields: list[InterfaceField] = Field(default_factory=list)
    constants: list[InterfaceConstant] = Field(default_factory=list)


class InterfaceDefinition(BaseModel):
    """One static interface file result."""

    name: str
    relative_path: str
    kind: str
    valid: bool
    sections: list[InterfaceSection] = Field(default_factory=list)
    referenced_types: list[str] = Field(default_factory=list)
    unresolved_types: list[str] = Field(default_factory=list)
    issues: list[ScanIssue] = Field(default_factory=list)


class InterfaceInspectionResult(BaseModel):
    """All selected interfaces for one package."""

    package_name: str | None
    relative_path: str | None
    interface_name: str | None = None
    valid: bool
    interfaces: list[InterfaceDefinition] = Field(default_factory=list)
    issues: list[ScanIssue] = Field(default_factory=list)
