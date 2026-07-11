"""Safe parsing of dependency-like package.xml declarations."""

import xml.etree.ElementTree as ET
from pathlib import Path

from ros2_workspace_mcp.models.dependency import DependencyDeclaration
from ros2_workspace_mcp.parsers.package_xml import MAX_PACKAGE_XML_BYTES, PackageXmlError
from ros2_workspace_mcp.security.files import SafeTextReadError, read_text_file_with_limit

DEPENDENCY_TAGS = frozenset(
    {
        "depend",
        "build_depend",
        "build_export_depend",
        "buildtool_depend",
        "exec_depend",
        "test_depend",
        "doc_depend",
        "conflict",
        "replace",
        "group_depend",
        "member_of_group",
    }
)


def parse_package_dependencies(root: Path, package_xml: Path) -> list[DependencyDeclaration]:
    """Return dependency declarations without evaluating conditions."""
    try:
        text = read_text_file_with_limit(root, package_xml, max_bytes=MAX_PACKAGE_XML_BYTES)
        document = ET.fromstring(text)
    except (SafeTextReadError, ET.ParseError) as exc:
        raise PackageXmlError("package.xml is not readable valid XML") from exc
    if document.tag != "package":
        raise PackageXmlError("package.xml root element must be <package>")

    declarations = []
    for item in document:
        if item.tag not in DEPENDENCY_TAGS or item.text is None:
            continue
        name = item.text.strip()
        if name:
            declarations.append(
                DependencyDeclaration(
                    name=name,
                    kind=item.tag,
                    condition=item.get("condition"),
                )
            )
    return sorted(
        declarations,
        key=lambda dependency: (
            dependency.name.casefold(),
            dependency.kind,
            dependency.condition or "",
        ),
    )
