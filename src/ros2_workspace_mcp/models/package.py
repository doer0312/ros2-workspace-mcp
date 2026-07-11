"""Models for detailed static package inspection."""

from pydantic import BaseModel, Field

from ros2_workspace_mcp.models.common import ScanIssue
from ros2_workspace_mcp.models.workspace import BuildTypeSource


class PackagePerson(BaseModel):
    """Manifest person metadata."""

    name: str
    email: str | None = None


class PackageUrl(BaseModel):
    """Manifest URL metadata."""

    url: str
    type: str | None = None


class PackageManifestDetails(BaseModel):
    """Detailed package.xml metadata without dependency analysis."""

    name: str | None
    version: str | None
    description: str | None
    package_format: str | None
    maintainers: list[PackagePerson]
    licenses: list[str]
    urls: list[PackageUrl]
    authors: list[PackagePerson]
    groups: list[str]
    member_of_groups: list[str]
    build_type: str | None


class BuildSystemInspection(BaseModel):
    """Static build-system evidence and conclusion."""

    manifest_build_type: str | None
    inferred_build_type: str
    build_type_source: BuildTypeSource
    evidence: list[str]
    conflict: bool
    has_cmake_lists: bool
    has_setup_py: bool
    has_setup_cfg: bool
    has_pyproject_toml: bool


class ExecutableSummary(BaseModel):
    """A statically discovered executable entry."""

    name: str
    target: str | None = None
    source: str
    dynamic: bool = False


class PackageInspectionResult(BaseModel):
    """Detailed JSON-safe inspection of one selected package."""

    name: str | None
    relative_path: str | None
    valid: bool
    manifest: PackageManifestDetails | None
    build_system: BuildSystemInspection | None
    executables: list[ExecutableSummary] = Field(default_factory=list)
    launch_files: list[str] = Field(default_factory=list)
    config_files: list[str] = Field(default_factory=list)
    interface_files: list[str] = Field(default_factory=list)
    robot_description_files: list[str] = Field(default_factory=list)
    test_files: list[str] = Field(default_factory=list)
    resource_files: list[str] = Field(default_factory=list)
    selection_candidates: list[str] = Field(default_factory=list)
    issues: list[ScanIssue] = Field(default_factory=list)
