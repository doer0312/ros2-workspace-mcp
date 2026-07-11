"""Structured models for ROS 2 workspace discovery."""

from enum import Enum

from pydantic import BaseModel, ConfigDict, model_validator

from ros2_workspace_mcp.models.common import ScanIssue


class BuildTypeSource(str, Enum):
    """How the reported build type was determined."""

    MANIFEST = "manifest"
    INFERRED = "inferred"
    UNKNOWN = "unknown"


class WorkspaceLayout(str, Enum):
    """Supported source directory layouts."""

    COLCON_WORKSPACE = "colcon_workspace"
    SOURCE_DIRECTORY = "source_directory"


class PackageManifest(BaseModel):
    """Relevant metadata parsed safely from package.xml."""

    model_config = ConfigDict(frozen=True)

    name: str | None
    version: str | None
    description: str | None
    package_format: str | None
    maintainer_count: int
    licenses: list[str]
    build_type: str | None


class PackageSummary(BaseModel):
    """A JSON-safe summary of one package.xml candidate directory."""

    name: str | None
    relative_path: str
    version: str | None
    description: str | None
    package_format: str | None
    build_type: str
    build_type_source: BuildTypeSource
    maintainer_count: int
    licenses: list[str]
    has_cmake_lists: bool
    has_setup_py: bool
    has_setup_cfg: bool
    valid: bool
    issues: list[ScanIssue]


class WorkspaceScanResult(BaseModel):
    """Complete JSON-safe result of a read-only workspace scan."""

    server_name: str
    server_version: str
    root_path: str
    scan_path: str
    layout: WorkspaceLayout
    package_count: int
    valid_package_count: int
    invalid_package_count: int
    packages: list[PackageSummary]
    duplicate_package_names: list[str]
    issues: list[ScanIssue]

    @model_validator(mode="after")
    def validate_counts(self) -> "WorkspaceScanResult":
        """Keep summary counts consistent with the package list."""
        if self.package_count != len(self.packages):
            raise ValueError("package_count must equal the number of packages")
        if self.valid_package_count + self.invalid_package_count != self.package_count:
            raise ValueError("valid and invalid counts must sum to package_count")
        return self
