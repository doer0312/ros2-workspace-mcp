"""Static URDF and unexpanded Xacro parsing and validation."""

import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from ros2_workspace_mcp.models.common import ScanIssue, Severity
from ros2_workspace_mcp.models.robot import (
    MeshReference,
    RobotDescriptionInspectionResult,
    RobotGeometry,
    RobotJoint,
    RobotLink,
    XacroInclude,
    XacroSummary,
)
from ros2_workspace_mcp.security.paths import (
    InvalidWorkspacePathError,
    PathOutsideRootError,
    resolve_within_root,
)

_DYNAMIC = re.compile(r"\$\{[^}]*\}|\$\([^)]*\)")
_XACRO_STANDARD = {"property", "macro", "arg", "include", "if", "unless", "insert_block"}


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _issue(
    severity: Severity, code: str, message: str, path: str, context: dict[str, Any] | None = None
) -> ScanIssue:
    return ScanIssue(
        severity=severity,
        code=code,
        message=message,
        path=path,
        context=context or {},
    )


def _floats(element: ET.Element | None) -> dict[str, float]:
    if element is None:
        return {}
    values = {}
    for name, value in element.attrib.items():
        try:
            values[name] = float(value)
        except ValueError:
            continue
    return values


def _geometry(element: ET.Element | None) -> RobotGeometry | None:
    if element is None:
        return None
    child = next(iter(element), None)
    if child is None:
        return None
    kind = _local(child.tag)
    dimensions = {key: value for key, value in child.attrib.items() if key != "filename"}
    return RobotGeometry(
        kind=kind,
        dimensions=dimensions,
        mesh_filename=child.get("filename") if kind == "mesh" else None,
    )


def _link(element: ET.Element) -> RobotLink:
    visuals = [
        geometry
        for visual in element.findall("visual")
        if (geometry := _geometry(visual.find("geometry")))
    ]
    collisions = [
        geometry
        for collision in element.findall("collision")
        if (geometry := _geometry(collision.find("geometry")))
    ]
    inertial_element = element.find("inertial")
    inertial = None
    if inertial_element is not None:
        inertial = {
            "mass": _floats(inertial_element.find("mass")),
            "inertia": _floats(inertial_element.find("inertia")),
        }
    return RobotLink(
        name=element.get("name", ""),
        visuals=visuals,
        collisions=collisions,
        inertial=inertial,
    )


def _joint(element: ET.Element) -> RobotJoint:
    origin = element.find("origin")
    axis = element.find("axis")
    mimic = element.find("mimic")
    mimic_data: dict[str, Any] | None = None
    if mimic is not None:
        mimic_data = {"joint": mimic.get("joint")}
        for key in ("multiplier", "offset"):
            if mimic.get(key) is not None:
                try:
                    mimic_data[key] = float(mimic.get(key, ""))
                except ValueError:
                    mimic_data[key] = mimic.get(key)
    return RobotJoint(
        name=element.get("name", ""),
        type=element.get("type"),
        parent=(element.find("parent").get("link") if element.find("parent") is not None else None),
        child=(element.find("child").get("link") if element.find("child") is not None else None),
        origin=dict(origin.attrib) if origin is not None else {},
        axis=axis.get("xyz") if axis is not None else None,
        limits=_floats(element.find("limit")),
        dynamics=_floats(element.find("dynamics")),
        safety_controller=_floats(element.find("safety_controller")),
        calibration=_floats(element.find("calibration")),
        mimic=mimic_data,
    )


def _cycles(links: set[str], joints: list[RobotJoint]) -> list[list[str]]:
    graph = {link: [] for link in links}
    for joint in joints:
        if joint.parent in graph and joint.child in graph:
            graph[joint.parent].append(joint.child)
    cycles: set[tuple[str, ...]] = set()

    def visit(node: str, path: list[str]) -> None:
        if node in path:
            cycle = path[path.index(node) :]
            rotations = [tuple(cycle[index:] + cycle[:index]) for index in range(len(cycle))]
            cycles.add(min(rotations))
            return
        for child in sorted(graph[node]):
            visit(child, [*path, node])

    for link in sorted(links):
        visit(link, [])
    return [list(cycle) for cycle in sorted(cycles)]


def _mesh_references(
    links: list[RobotLink], root: Path, description_path: Path, issues: list[ScanIssue]
) -> list[MeshReference]:
    references = []
    for geometry in [
        geometry
        for link in links
        for geometry in [*link.visuals, *link.collisions]
        if geometry.mesh_filename
    ]:
        filename = geometry.mesh_filename or ""
        if filename.startswith("package://"):
            references.append(MeshReference(filename=filename, package_uri=True, resolvable=None))
            continue
        try:
            mesh = resolve_within_root(
                root,
                description_path.parent / filename,
                require_directory=False,
            )
            references.append(
                MeshReference(filename=filename, package_uri=False, resolvable=mesh.is_file())
            )
        except PathOutsideRootError:
            references.append(MeshReference(filename=filename, package_uri=False, resolvable=False))
            issues.append(
                _issue(
                    Severity.ERROR,
                    "MESH_PATH_OUTSIDE_ROOT",
                    "Relative mesh path resolves outside the workspace.",
                    description_path.relative_to(root).as_posix(),
                )
            )
        except InvalidWorkspacePathError:
            references.append(MeshReference(filename=filename, package_uri=False, resolvable=False))
            issues.append(
                _issue(
                    Severity.WARNING,
                    "MESH_NOT_FOUND",
                    "Relative mesh path was not found.",
                    description_path.relative_to(root).as_posix(),
                    {"mesh": filename},
                )
            )
    return sorted(references, key=lambda item: item.filename)


def _validate_urdf(
    document: ET.Element, root: Path, path: Path
) -> RobotDescriptionInspectionResult:
    relative = path.relative_to(root).as_posix()
    issues: list[ScanIssue] = []
    link_elements = document.findall("link")
    joint_elements = document.findall("joint")
    links = [_link(item) for item in link_elements]
    joints = [_joint(item) for item in joint_elements]
    link_names = [link.name for link in links]
    joint_names = [joint.name for joint in joints]
    link_set = set(link_names)
    for name in sorted({name for name in link_names if link_names.count(name) > 1}):
        issues.append(
            _issue(
                Severity.ERROR, "DUPLICATE_LINK", "Duplicate link name.", relative, {"name": name}
            )
        )
    for name in sorted({name for name in joint_names if joint_names.count(name) > 1}):
        issues.append(
            _issue(
                Severity.ERROR, "DUPLICATE_JOINT", "Duplicate joint name.", relative, {"name": name}
            )
        )
    children: set[str] = set()
    parents: set[str] = set()
    for joint in joints:
        if not joint.parent or not joint.child:
            issues.append(
                _issue(
                    Severity.ERROR,
                    "MISSING_JOINT_LINK",
                    "Joint parent or child is missing.",
                    relative,
                    {"joint": joint.name},
                )
            )
        if joint.parent:
            parents.add(joint.parent)
            if joint.parent not in link_set:
                issues.append(
                    _issue(
                        Severity.ERROR,
                        "JOINT_PARENT_NOT_FOUND",
                        "Joint parent link does not exist.",
                        relative,
                        {"joint": joint.name},
                    )
                )
        if joint.child:
            children.add(joint.child)
            if joint.child not in link_set:
                issues.append(
                    _issue(
                        Severity.ERROR,
                        "JOINT_CHILD_NOT_FOUND",
                        "Joint child link does not exist.",
                        relative,
                        {"joint": joint.name},
                    )
                )
        if (
            joint.limits.get("lower") is not None
            and joint.limits.get("upper") is not None
            and joint.limits["lower"] > joint.limits["upper"]
        ):
            issues.append(
                _issue(
                    Severity.ERROR,
                    "INVALID_JOINT_LIMIT",
                    "Joint lower limit exceeds upper limit.",
                    relative,
                    {"joint": joint.name},
                )
            )
        if joint.type in {"revolute", "prismatic", "continuous"} and not joint.limits:
            issues.append(
                _issue(
                    Severity.WARNING,
                    "MISSING_JOINT_LIMIT",
                    "Non-fixed joint has no limit declaration.",
                    relative,
                    {"joint": joint.name},
                )
            )
        if joint.mimic and joint.mimic.get("joint") not in set(joint_names):
            issues.append(
                _issue(
                    Severity.ERROR,
                    "MIMIC_TARGET_NOT_FOUND",
                    "Mimic target joint does not exist.",
                    relative,
                    {"joint": joint.name},
                )
            )
    roots = sorted(link_set - children)
    if len(roots) > 1:
        issues.append(
            _issue(
                Severity.ERROR, "MULTIPLE_ROOT_LINKS", "Robot has multiple root links.", relative
            )
        )
    elif not roots and links:
        issues.append(_issue(Severity.ERROR, "NO_ROOT_LINK", "Robot has no root link.", relative))
    for cycle in _cycles(link_set, joints):
        issues.append(
            _issue(
                Severity.ERROR,
                "KINEMATIC_CYCLE",
                "Kinematic cycle detected.",
                relative,
                {"links": cycle},
            )
        )
    meshes = _mesh_references(links, root, path, issues)
    return RobotDescriptionInspectionResult(
        relative_path=relative,
        format="urdf",
        robot_name=document.get("name"),
        valid=not any(issue.severity is Severity.ERROR for issue in issues),
        expanded=True,
        links=sorted(links, key=lambda item: item.name),
        joints=sorted(joints, key=lambda item: item.name),
        root_links=roots,
        leaf_links=sorted(link_set - parents),
        transmissions=sorted(item.get("name", "") for item in document.findall("transmission")),
        has_gazebo_extensions=bool(document.findall("gazebo")),
        mesh_references=meshes,
        issues=issues,
    )


def parse_robot_description_xml(
    text: str,
    *,
    root: Path,
    path: Path,
    format_name: str,
) -> RobotDescriptionInspectionResult:
    """Parse URDF or summarize unexpanded Xacro XML."""
    relative = path.relative_to(root).as_posix()
    try:
        document = ET.fromstring(text)
    except ET.ParseError:
        return RobotDescriptionInspectionResult(
            relative_path=relative,
            format=format_name,
            valid=False,
            expanded=format_name == "urdf",
            issues=[_issue(Severity.ERROR, "INVALID_ROBOT_XML", "Robot XML is invalid.", relative)],
        )
    if _local(document.tag) != "robot":
        return RobotDescriptionInspectionResult(
            relative_path=relative,
            format=format_name,
            valid=False,
            expanded=format_name == "urdf",
            issues=[
                _issue(
                    Severity.ERROR, "INVALID_ROBOT_ROOT", "Root element must be <robot>.", relative
                )
            ],
        )
    if format_name == "urdf":
        return _validate_urdf(document, root, path)

    dynamic_expressions = sorted(
        {
            match.group(0)
            for element in document.iter()
            for value in [*element.attrib.values(), element.text or ""]
            for match in _DYNAMIC.finditer(value)
        }
    )
    properties: list[str] = []
    macros: list[str] = []
    arguments: list[str] = []
    macro_calls: list[str] = []
    includes: list[XacroInclude] = []
    for element in document.iter():
        name = _local(element.tag)
        if name == "property" and element.get("name"):
            properties.append(element.get("name", ""))
        elif name == "macro" and element.get("name"):
            macros.append(element.get("name", ""))
        elif name == "arg" and element.get("name"):
            arguments.append(element.get("name", ""))
        elif name == "include":
            filename = element.get("filename")
            dynamic = bool(filename and _DYNAMIC.search(filename))
            resolvable = False
            if filename and not dynamic:
                try:
                    resolve_within_root(root, path.parent / filename, require_directory=False)
                    resolvable = True
                except (InvalidWorkspacePathError, PathOutsideRootError):
                    pass
            includes.append(XacroInclude(filename=filename, dynamic=dynamic, resolvable=resolvable))
        elif "}" in element.tag and name not in _XACRO_STANDARD:
            macro_calls.append(name)
    static_children = [
        element
        for element in document
        if _local(element.tag) in {"link", "joint"}
        and not any(_DYNAMIC.search(value) for value in element.attrib.values())
    ]
    static_document = ET.Element("robot", {"name": document.get("name", "")})
    static_document.extend(static_children)
    urdf_part = _validate_urdf(static_document, root, path)
    urdf_part.format = "xacro"
    urdf_part.expanded = False
    urdf_part.xacro_summary = XacroSummary(
        properties=sorted(properties),
        macros=sorted(macros),
        arguments=sorted(arguments),
        includes=sorted(includes, key=lambda item: item.filename or ""),
        macro_calls=sorted(set(macro_calls)),
        dynamic_expressions=dynamic_expressions,
        contains_dynamic_expressions=bool(dynamic_expressions),
    )
    return urdf_part
