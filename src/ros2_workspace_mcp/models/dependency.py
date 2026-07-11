"""Models for package dependency declarations and graph analysis."""

from pydantic import BaseModel, Field

from ros2_workspace_mcp.models.common import ScanIssue


class DependencyDeclaration(BaseModel):
    """One package.xml dependency-like declaration."""

    name: str
    kind: str
    condition: str | None = None


class PackageDependencies(BaseModel):
    """Declarations for one workspace package."""

    package_name: str
    relative_path: str
    dependencies: list[DependencyDeclaration]


class DependencyEdge(BaseModel):
    """A directed workspace dependency edge."""

    source: str
    target: str
    kinds: list[str]


class DependencyAnalysisResult(BaseModel):
    """JSON-safe dependency graph result."""

    scope: str
    selected_package: str | None = None
    packages: list[PackageDependencies] = Field(default_factory=list)
    workspace_dependencies: list[str] = Field(default_factory=list)
    external_dependencies: list[str] = Field(default_factory=list)
    missing_workspace_references: list[str] = Field(default_factory=list)
    dependency_edges: list[DependencyEdge] = Field(default_factory=list)
    topological_order: list[str] = Field(default_factory=list)
    cycles: list[list[str]] = Field(default_factory=list)
    issues: list[ScanIssue] = Field(default_factory=list)
