from pathlib import Path

from ros2_workspace_mcp.parsers.package_details import parse_package_manifest_details


def test_detailed_manifest_metadata(tmp_path: Path) -> None:
    manifest = tmp_path / "package.xml"
    manifest.write_text(
        '<package format="3"><name>demo</name><version>1.2.3</version>'
        "<description> Detailed\n package </description>"
        '<maintainer email="maint@example.com">Maintainer</maintainer>'
        '<author email="author@example.com">Author</author><license>MIT</license>'
        '<url type="repository">https://example.invalid/repo</url>'
        "<group>demo_group</group><member_of_group>rosidl_interface_packages</member_of_group>"
        "<export><build_type>ament_cmake</build_type></export></package>",
        encoding="utf-8",
    )

    details = parse_package_manifest_details(tmp_path, manifest)

    assert details.name == "demo"
    assert details.description == "Detailed package"
    assert details.maintainers[0].email == "maint@example.com"
    assert details.authors[0].name == "Author"
    assert details.urls[0].type == "repository"
    assert details.groups == ["demo_group"]
    assert details.member_of_groups == ["rosidl_interface_packages"]
    assert details.build_type == "ament_cmake"
