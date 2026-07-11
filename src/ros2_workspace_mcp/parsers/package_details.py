"""Detailed package.xml metadata parsing."""

import re
import xml.etree.ElementTree as ET
from pathlib import Path

from ros2_workspace_mcp.models.package import (
    PackageManifestDetails,
    PackagePerson,
    PackageUrl,
)
from ros2_workspace_mcp.parsers.package_xml import MAX_PACKAGE_XML_BYTES, PackageXmlError
from ros2_workspace_mcp.security.files import SafeTextReadError, read_text_file_with_limit

_WHITESPACE = re.compile(r"\s+")


def _text(element: ET.Element | None, *, normalize: bool = False) -> str | None:
    if element is None or element.text is None:
        return None
    value = element.text.strip()
    return (_WHITESPACE.sub(" ", value) if normalize else value) or None


def parse_package_manifest_details(root: Path, package_xml: Path) -> PackageManifestDetails:
    """Parse detailed non-dependency manifest metadata."""
    try:
        text = read_text_file_with_limit(root, package_xml, max_bytes=MAX_PACKAGE_XML_BYTES)
        document = ET.fromstring(text)
    except (SafeTextReadError, ET.ParseError) as exc:
        raise PackageXmlError("package.xml is not readable valid XML") from exc
    if document.tag != "package":
        raise PackageXmlError("package.xml root element must be <package>")

    export = document.find("export")
    build_type = _text(export.find("build_type")) if export is not None else None
    maintainers = [
        PackagePerson(name=name, email=item.get("email"))
        for item in document.findall("maintainer")
        if (name := _text(item))
    ]
    authors = [
        PackagePerson(name=name, email=item.get("email"))
        for item in document.findall("author")
        if (name := _text(item))
    ]
    urls = [
        PackageUrl(url=value, type=item.get("type"))
        for item in document.findall("url")
        if (value := _text(item))
    ]
    return PackageManifestDetails(
        name=_text(document.find("name")),
        version=_text(document.find("version")),
        description=_text(document.find("description"), normalize=True),
        package_format=document.get("format"),
        maintainers=maintainers,
        licenses=[value for item in document.findall("license") if (value := _text(item))],
        urls=urls,
        authors=authors,
        groups=[value for item in document.findall("group") if (value := _text(item))],
        member_of_groups=[
            value for item in document.findall("member_of_group") if (value := _text(item))
        ],
        build_type=build_type,
    )
