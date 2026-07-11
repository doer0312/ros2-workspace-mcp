from collections.abc import Callable
from pathlib import Path

import pytest

from ros2_workspace_mcp.parsers.package_xml import PackageXmlError, parse_package_xml


def test_parses_minimal_valid_manifest(tmp_path: Path, write_package: Callable[..., Path]) -> None:
    package = write_package(tmp_path / "pkg")

    manifest = parse_package_xml(tmp_path, package / "package.xml")

    assert manifest.name == "demo_pkg"
    assert manifest.version == "0.1.0"
    assert manifest.package_format == "3"
    assert manifest.maintainer_count == 1


@pytest.mark.parametrize("build_type", ["ament_cmake", "ament_python"])
def test_parses_manifest_build_type(
    tmp_path: Path, write_package: Callable[..., Path], build_type: str
) -> None:
    package = write_package(tmp_path / "pkg", build_type=build_type)

    assert parse_package_xml(tmp_path, package / "package.xml").build_type == build_type


def test_missing_name_is_not_guessed(tmp_path: Path) -> None:
    manifest_path = tmp_path / "package.xml"
    manifest_path.write_text(
        "<package><version>1.0.0</version><description>demo</description></package>",
        encoding="utf-8",
    )

    assert parse_package_xml(tmp_path, manifest_path).name is None


def test_invalid_xml_raises_clear_error(tmp_path: Path) -> None:
    manifest_path = tmp_path / "package.xml"
    manifest_path.write_text("<package>", encoding="utf-8")

    with pytest.raises(PackageXmlError, match="valid XML"):
        parse_package_xml(tmp_path, manifest_path)


def test_multiple_licenses_are_preserved(
    tmp_path: Path, write_package: Callable[..., Path]
) -> None:
    package = write_package(tmp_path / "pkg", licenses=("Apache-2.0", "MIT"))

    assert parse_package_xml(tmp_path, package / "package.xml").licenses == [
        "Apache-2.0",
        "MIT",
    ]


def test_description_whitespace_is_normalized(
    tmp_path: Path, write_package: Callable[..., Path]
) -> None:
    package = write_package(tmp_path / "pkg", description="  A\n   spaced\t description  ")

    assert parse_package_xml(tmp_path, package / "package.xml").description == (
        "A spaced description"
    )


def test_external_entity_is_not_expanded(tmp_path: Path) -> None:
    secret = tmp_path.parent / "secret.txt"
    secret.write_text("secret-value", encoding="utf-8")
    manifest_path = tmp_path / "package.xml"
    manifest_path.write_text(
        '<!DOCTYPE package [<!ENTITY xxe SYSTEM "file:///secret.txt">]>'
        "<package><name>&xxe;</name></package>",
        encoding="utf-8",
    )

    with pytest.raises(PackageXmlError):
        parse_package_xml(tmp_path, manifest_path)
