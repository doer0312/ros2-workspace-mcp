from pathlib import Path

from ros2_workspace_mcp.parsers.robot import parse_robot_description_xml


def _parse(tmp_path: Path, text: str, name: str = "robot.urdf"):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return parse_robot_description_xml(
        text,
        root=tmp_path,
        path=path,
        format_name="xacro" if name.endswith("xacro") else "urdf",
    )


def test_minimal_urdf_and_fixed_chain(tmp_path: Path) -> None:
    result = _parse(
        tmp_path,
        """
<robot name="arm">
  <link name="base"/><link name="tip"/>
  <joint name="fixed" type="fixed"><parent link="base"/><child link="tip"/>
    <origin xyz="0 0 1" rpy="0 0 0"/><axis xyz="0 0 1"/></joint>
</robot>
""",
    )

    assert result.valid
    assert result.robot_name == "arm"
    assert result.root_links == ["base"]
    assert result.leaf_links == ["tip"]
    assert result.joints[0].origin["xyz"] == "0 0 1"


def test_revolute_limit_and_invalid_limit(tmp_path: Path) -> None:
    result = _parse(
        tmp_path,
        """
<robot name="arm"><link name="a"/><link name="b"/>
<joint name="joint" type="revolute"><parent link="a"/><child link="b"/>
<limit lower="2" upper="1" effort="1" velocity="1"/></joint></robot>
""",
    )

    assert result.joints[0].limits["lower"] == 2
    assert any(issue.code == "INVALID_JOINT_LIMIT" for issue in result.issues)


def test_missing_links_multiple_roots_and_cycle(tmp_path: Path) -> None:
    missing = _parse(
        tmp_path,
        '<robot name="bad"><link name="a"/><link name="orphan"/><link name="orphan2"/>'
        '<joint name="j" type="fixed"><parent link="missing"/><child link="a"/></joint></robot>',
    )
    cycle = _parse(
        tmp_path,
        '<robot name="cycle"><link name="a"/><link name="b"/>'
        '<joint name="ab" type="fixed"><parent link="a"/><child link="b"/></joint>'
        '<joint name="ba" type="fixed"><parent link="b"/><child link="a"/></joint></robot>',
        "cycle.urdf",
    )

    assert {issue.code for issue in missing.issues} >= {
        "JOINT_PARENT_NOT_FOUND",
        "MULTIPLE_ROOT_LINKS",
    }
    assert {issue.code for issue in cycle.issues} >= {"NO_ROOT_LINK", "KINEMATIC_CYCLE"}


def test_mimic_target_missing(tmp_path: Path) -> None:
    result = _parse(
        tmp_path,
        '<robot name="arm"><link name="a"/><link name="b"/>'
        '<joint name="j" type="fixed"><parent link="a"/><child link="b"/>'
        '<mimic joint="missing"/></joint></robot>',
    )

    assert any(issue.code == "MIMIC_TARGET_NOT_FOUND" for issue in result.issues)


def test_mesh_package_uri_and_relative_resolution(tmp_path: Path) -> None:
    meshes = tmp_path / "meshes"
    meshes.mkdir()
    (meshes / "body.stl").write_bytes(b"mesh")
    result = _parse(
        tmp_path,
        """
<robot name="mesh"><link name="base">
<visual><geometry><mesh filename="meshes/body.stl"/></geometry></visual>
<collision><geometry><mesh filename="package://demo/meshes/body.stl"/></geometry></collision>
</link></robot>
""",
    )

    assert result.mesh_references[0].resolvable is True
    assert result.mesh_references[1].package_uri
    assert result.mesh_references[1].resolvable is None


def test_xacro_is_unexpanded_and_summarized(tmp_path: Path) -> None:
    result = _parse(
        tmp_path,
        """
<robot name="x" xmlns:xacro="http://www.ros.org/wiki/xacro">
  <xacro:arg name="prefix" default=""/>
  <xacro:property name="length" value="1.0"/>
  <xacro:macro name="make_link" params="name"><link name="${name}"/></xacro:macro>
  <xacro:make_link name="${prefix}tip"/>
  <link name="base"/>
</robot>
""",
        "robot.xacro",
    )

    assert result.valid
    assert not result.expanded
    assert result.xacro_summary is not None
    assert result.xacro_summary.properties == ["length"]
    assert result.xacro_summary.macros == ["make_link"]
    assert result.xacro_summary.macro_calls == ["make_link"]
    assert result.xacro_summary.contains_dynamic_expressions
    assert [link.name for link in result.links] == ["base"]
