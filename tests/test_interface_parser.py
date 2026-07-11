from ros2_workspace_mcp.models.interface import ArrayKind
from ros2_workspace_mcp.parsers.interfaces import parse_interface_text


def test_msg_fields_constants_defaults_arrays_and_comments() -> None:
    result = parse_interface_text(
        """
        # comment
        int32 count 5
        string<=20 name
        float64[10] fixed
        uint8[] data
        int16[<=4] bounded
        int32 ANSWER=42
        geometry_msgs/Pose pose
        """,
        kind="msg",
        relative_path="src/demo/msg/Demo.msg",
    )

    fields = result.sections[0].fields
    assert result.valid
    assert fields[0].default_value == "5"
    assert fields[1].string_bound == 20
    assert fields[2].array_kind is ArrayKind.FIXED
    assert fields[2].array_bound == 10
    assert fields[3].array_kind is ArrayKind.UNBOUNDED
    assert fields[4].array_kind is ArrayKind.BOUNDED
    assert fields[4].array_bound == 4
    assert result.sections[0].constants[0].name == "ANSWER"
    assert fields[5].package_name == "geometry_msgs"


def test_srv_sections() -> None:
    result = parse_interface_text(
        "int64 a\n---\nint64 sum\n",
        kind="srv",
        relative_path="demo/srv/Add.srv",
    )

    assert result.valid
    assert [section.name for section in result.sections] == ["request", "response"]


def test_action_sections() -> None:
    result = parse_interface_text(
        "int32 target\n---\nbool success\n---\nint32 progress\n",
        kind="action",
        relative_path="demo/action/Move.action",
    )

    assert result.valid
    assert [section.name for section in result.sections] == [
        "goal",
        "result",
        "feedback",
    ]


def test_wrong_separator_count_and_invalid_field() -> None:
    result = parse_interface_text(
        "not-a-field\n---\n---\n",
        kind="srv",
        relative_path="demo/srv/Bad.srv",
    )

    assert not result.valid
    assert {issue.code for issue in result.issues} == {
        "INVALID_INTERFACE_FIELD",
        "INVALID_INTERFACE_SEPARATOR",
    }
