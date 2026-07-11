"""Bounded, non-executing package.xml parsing."""

import re
import xml.etree.ElementTree as ET
from pathlib import Path

from ros2_workspace_mcp.models.workspace import PackageManifest
from ros2_workspace_mcp.security.files import SafeTextReadError, read_text_file_with_limit

MAX_PACKAGE_XML_BYTES = 1024 * 1024
_WHITESPACE = re.compile(r"\s+")


class PackageXmlError(Exception):
    """Raised when package.xml cannot be read or parsed safely."""


def _text(element: ET.Element | None, *, normalize: bool = False) -> str | None:
    if element is None or element.text is None:
        return None
    value = element.text.strip()
    if normalize:
        value = _WHITESPACE.sub(" ", value)
    return value or None


def parse_package_xml(root: Path, package_xml: Path) -> PackageManifest:
    """Parse the small metadata subset used by scan_workspace."""
    try:
        xml_text = read_text_file_with_limit(root, package_xml, max_bytes=MAX_PACKAGE_XML_BYTES)
        document = ET.fromstring(xml_text)
    except (SafeTextReadError, ET.ParseError) as exc:
        raise PackageXmlError("package.xml is not readable valid XML") from exc

    if document.tag != "package":
        raise PackageXmlError("package.xml root element must be <package>")

    export = document.find("export")
    build_type = _text(export.find("build_type")) if export is not None else None
    licenses = [value for element in document.findall("license") if (value := _text(element))]
    return PackageManifest(
        name=_text(document.find("name")),
        version=_text(document.find("version")),
        description=_text(document.find("description"), normalize=True),
        package_format=document.get("format"),
        maintainer_count=sum(1 for item in document.findall("maintainer") if _text(item)),
        licenses=licenses,
        build_type=build_type,
    )
