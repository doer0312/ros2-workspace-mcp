from ros2_workspace_mcp.parsers.launch import (
    parse_python_launch,
    parse_xml_launch,
    parse_yaml_launch,
)


def test_python_launch_static_entities_and_process_not_executed() -> None:
    result = parse_python_launch(
        """
LaunchDescription([
    DeclareLaunchArgument('mode', default_value='safe'),
    Node(package='demo', executable='node', name='demo_node',
         namespace='/robot', parameters=[{'rate': 10}],
         remappings=[('/in', '/out')], arguments=['--flag']),
    IncludeLaunchDescription(PythonLaunchDescriptionSource('child.launch.py')),
    SetEnvironmentVariable(name='MODE', value='test'),
    ExecuteProcess(cmd=['must-not-run', '--danger']),
])
""",
        "demo/launch/demo.launch.py",
    )

    assert result.valid
    assert result.nodes[0].package == "demo"
    assert result.nodes[0].parameters == [{"rate": 10}]
    assert result.arguments[0].name == "mode"
    assert result.includes[0].path == "child.launch.py"
    assert result.environment_changes[0].name == "MODE"
    assert result.processes[0].command == ["must-not-run", "--danger"]


def test_python_dynamic_expressions_are_not_evaluated() -> None:
    result = parse_python_launch(
        "Node(package=LaunchConfiguration('pkg'), executable=get_executable())",
        "demo.launch.py",
    )

    assert result.nodes[0].dynamic
    assert "get_executable()" in result.dynamic_expressions


def test_invalid_python_launch() -> None:
    result = parse_python_launch("def broken(", "broken.launch.py")

    assert not result.valid
    assert result.issues[0].code == "INVALID_PYTHON_LAUNCH"


def test_xml_launch_entities() -> None:
    result = parse_xml_launch(
        """
<launch>
  <arg name="mode" default="safe"/>
  <node pkg="demo" exec="node" name="demo"><param name="rate" value="10"/>
    <remap from="in" to="out"/></node>
  <include file="child.launch.xml"/>
  <set_env name="MODE" value="test"/>
  <executable cmd="must-not-run"/>
</launch>
""",
        "demo.launch.xml",
    )

    assert result.valid
    assert result.nodes[0].executable == "node"
    assert result.includes[0].path == "child.launch.xml"
    assert result.processes[0].command == "must-not-run"


def test_invalid_xml_launch() -> None:
    assert not parse_xml_launch("<launch>", "bad.launch.xml").valid


def test_yaml_launch_uses_safe_structures() -> None:
    result = parse_yaml_launch(
        """
launch:
  - node: {pkg: demo, exec: node, name: demo}
  - arg: {name: mode, default: safe}
  - include: {file: child.launch.yaml}
  - execute_process: {cmd: [must-not-run]}
""",
        "demo.launch.yaml",
    )

    assert result.valid
    assert result.nodes[0].package == "demo"
    assert result.arguments[0].default == "safe"
    assert result.processes[0].command == ["must-not-run"]


def test_unsafe_or_invalid_yaml_is_rejected() -> None:
    result = parse_yaml_launch(
        "!!python/object/apply:os.system ['must-not-run']",
        "bad.launch.yaml",
    )

    assert not result.valid
    assert result.issues[0].code == "INVALID_YAML_LAUNCH"
