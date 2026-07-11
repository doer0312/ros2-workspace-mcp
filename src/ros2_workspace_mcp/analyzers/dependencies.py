"""Workspace dependency graph analysis."""

from collections import Counter

from ros2_workspace_mcp.analyzers.package_selector import (
    PackageSelectionError,
    resolve_package_selector,
)
from ros2_workspace_mcp.analyzers.workspace import analyze_workspace
from ros2_workspace_mcp.config import ServerSettings
from ros2_workspace_mcp.models.common import ScanIssue, Severity
from ros2_workspace_mcp.models.dependency import (
    DependencyAnalysisResult,
    DependencyEdge,
    PackageDependencies,
)
from ros2_workspace_mcp.parsers.dependencies import parse_package_dependencies
from ros2_workspace_mcp.parsers.package_details import parse_package_manifest_details
from ros2_workspace_mcp.parsers.package_xml import PackageXmlError


def _issue(code: str, message: str, path: str, package_name: str | None = None) -> ScanIssue:
    return ScanIssue(
        severity=Severity.ERROR,
        code=code,
        message=message,
        path=path,
        package_name=package_name,
    )


def _strongly_connected_cycles(graph: dict[str, set[str]]) -> list[list[str]]:
    index = 0
    indices: dict[str, int] = {}
    lowlinks: dict[str, int] = {}
    stack: list[str] = []
    on_stack: set[str] = set()
    components: list[list[str]] = []

    def visit(node: str) -> None:
        nonlocal index
        indices[node] = index
        lowlinks[node] = index
        index += 1
        stack.append(node)
        on_stack.add(node)
        for target in sorted(graph[node]):
            if target not in indices:
                visit(target)
                lowlinks[node] = min(lowlinks[node], lowlinks[target])
            elif target in on_stack:
                lowlinks[node] = min(lowlinks[node], indices[target])
        if lowlinks[node] == indices[node]:
            component = []
            while stack:
                member = stack.pop()
                on_stack.remove(member)
                component.append(member)
                if member == node:
                    break
            if len(component) > 1 or node in graph[node]:
                components.append(sorted(component))

    for node in sorted(graph):
        if node not in indices:
            visit(node)
    return sorted(components)


def _topology(graph: dict[str, set[str]]) -> tuple[list[str], list[list[str]]]:
    remaining = {node: len(targets) for node, targets in graph.items()}
    ready = sorted(node for node, count in remaining.items() if count == 0)
    order: list[str] = []
    while ready:
        node = ready.pop(0)
        order.append(node)
        for dependent in sorted(graph):
            if node in graph[dependent]:
                remaining[dependent] -= 1
                if remaining[dependent] == 0:
                    ready.append(dependent)
                    ready.sort()
    return order, _strongly_connected_cycles(graph)


def _reachable(start: str, graph: dict[str, set[str]]) -> set[str]:
    result: set[str] = set()
    pending = [start]
    while pending:
        node = pending.pop()
        if node in result:
            continue
        result.add(node)
        pending.extend(sorted(graph.get(node, set()), reverse=True))
    return result


def analyze_dependencies(
    settings: ServerSettings,
    *,
    package_name: str | None = None,
    relative_path: str | None = None,
) -> DependencyAnalysisResult:
    """Analyze declared dependencies without ROS, rosdep, or network access."""
    if package_name is not None and relative_path is not None:
        return DependencyAnalysisResult(
            scope="package",
            issues=[
                _issue(
                    "INVALID_PACKAGE_SELECTOR",
                    "Provide at most one of package_name or relative_path.",
                    ".",
                )
            ],
        )

    selected_path: str | None = None
    selected_name: str | None = None
    if package_name is not None or relative_path is not None:
        try:
            package_dir, selected_path = resolve_package_selector(
                settings,
                package_name=package_name,
                relative_path=relative_path,
            )
            selected_name = parse_package_manifest_details(
                settings.root_path, package_dir / "package.xml"
            ).name
        except PackageSelectionError as exc:
            return DependencyAnalysisResult(
                scope="package",
                issues=[_issue(exc.code, str(exc), ".")],
            )
        except PackageXmlError as exc:
            return DependencyAnalysisResult(
                scope="package",
                issues=[_issue("INVALID_PACKAGE_XML", str(exc), selected_path or ".")],
            )

    scan = analyze_workspace(settings)
    named = [package for package in scan.packages if package.valid and package.name]
    counts = Counter(package.name for package in named)
    unique_names = {name for name, count in counts.items() if count == 1}
    issues = [
        issue
        for issue in scan.issues
        if issue.severity is Severity.ERROR or issue.code == "DUPLICATE_PACKAGE_NAME"
    ]
    packages: list[PackageDependencies] = []
    for package in named:
        if package.name not in unique_names and package.relative_path != selected_path:
            continue
        try:
            declarations = parse_package_dependencies(
                settings.root_path,
                settings.root_path / package.relative_path / "package.xml",
            )
        except PackageXmlError as exc:
            issues.append(
                _issue(
                    "INVALID_PACKAGE_XML",
                    str(exc),
                    f"{package.relative_path}/package.xml",
                    package.name,
                )
            )
            continue
        packages.append(
            PackageDependencies(
                package_name=package.name,
                relative_path=package.relative_path,
                dependencies=declarations,
            )
        )

    graph: dict[str, set[str]] = {name: set() for name in unique_names}
    edge_kinds: dict[tuple[str, str], set[str]] = {}
    external: set[str] = set()
    workspace_dependencies: set[str] = set()
    ignored_kinds = {"conflict", "replace", "member_of_group"}
    for package in packages:
        graph.setdefault(package.package_name, set())
        for dependency in package.dependencies:
            if dependency.kind in ignored_kinds:
                continue
            if dependency.name in unique_names:
                graph[package.package_name].add(dependency.name)
                workspace_dependencies.add(dependency.name)
                edge_kinds.setdefault((package.package_name, dependency.name), set()).add(
                    dependency.kind
                )
            else:
                external.add(dependency.name)

    if selected_name:
        scope_names = _reachable(selected_name, graph)
        graph = {
            name: {target for target in targets if target in scope_names}
            for name, targets in graph.items()
            if name in scope_names
        }
        packages = [package for package in packages if package.package_name in scope_names]
        edge_kinds = {
            edge: kinds
            for edge, kinds in edge_kinds.items()
            if edge[0] in scope_names and edge[1] in scope_names
        }
        workspace_dependencies &= scope_names
        external = {
            dependency.name
            for package in packages
            for dependency in package.dependencies
            if dependency.name not in unique_names and dependency.kind not in ignored_kinds
        }

    order, cycles = _topology(graph)
    for cycle in cycles:
        issues.append(
            ScanIssue(
                severity=Severity.ERROR,
                code="DEPENDENCY_CYCLE",
                message="Workspace dependency cycle detected.",
                path=".",
                context={"packages": cycle},
            )
        )
    edges = [
        DependencyEdge(source=source, target=target, kinds=sorted(kinds))
        for (source, target), kinds in sorted(edge_kinds.items())
    ]
    return DependencyAnalysisResult(
        scope="package" if selected_name else "workspace",
        selected_package=selected_name,
        packages=sorted(packages, key=lambda item: (item.package_name, item.relative_path)),
        workspace_dependencies=sorted(workspace_dependencies),
        external_dependencies=sorted(external),
        dependency_edges=edges,
        topological_order=order,
        cycles=cycles,
        issues=issues,
    )
