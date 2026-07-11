from pathlib import Path

from ros2_workspace_mcp.parsers.dependencies import DEPENDENCY_TAGS, parse_package_dependencies


def test_parses_all_dependency_tags_and_conditions(tmp_path: Path) -> None:
    declarations = "".join(
        f'<{tag} condition="$ROS_VERSION == 2">{tag}_pkg</{tag}>' for tag in sorted(DEPENDENCY_TAGS)
    )
    manifest = tmp_path / "package.xml"
    manifest.write_text(f"<package>{declarations}</package>", encoding="utf-8")

    result = parse_package_dependencies(tmp_path, manifest)

    assert {dependency.kind for dependency in result} == DEPENDENCY_TAGS
    assert all(dependency.condition == "$ROS_VERSION == 2" for dependency in result)
    depend = next(item for item in result if item.kind == "depend")
    assert depend.name == "depend_pkg"
