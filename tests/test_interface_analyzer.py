import json
from collections.abc import Callable
from pathlib import Path

from ros2_workspace_mcp.analyzers.interfaces import inspect_interfaces
from ros2_workspace_mcp.config import ServerSettings
from ros2_workspace_mcp.models.interface import InterfaceTypeScope
from ros2_workspace_mcp.parsers.interfaces import INTERFACE_MAX_BYTES


def _interface(package: Path, relative: str, text: str) -> None:
    path = package / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_all_interfaces_and_type_resolution(
    tmp_path: Path, write_package: Callable[..., Path]
) -> None:
    common = write_package(tmp_path / "src" / "common", name="common")
    demo = write_package(tmp_path / "src" / "demo", name="demo")
    _interface(common, "msg/Shared.msg", "string value\n")
    _interface(demo, "msg/Local.msg", "int32 value\n")
    _interface(
        demo,
        "msg/Uses.msg",
        "Local local\ncommon/Shared shared\ngeometry_msgs/Pose pose\n"
        "builtin_interfaces/Time stamp\nMissing missing\n",
    )
    _interface(demo, "srv/Reset.srv", "bool force\n---\nbool success\n")
    _interface(demo, "action/Move.action", "int32 goal\n---\nbool ok\n---\nint32 state\n")

    result = inspect_interfaces(ServerSettings(root_path=tmp_path), package_name="demo")

    assert len(result.interfaces) == 4
    uses = next(item for item in result.interfaces if item.name == "Uses")
    scopes = [field.type_scope for field in uses.sections[0].fields]
    assert scopes == [
        InterfaceTypeScope.WORKSPACE,
        InterfaceTypeScope.WORKSPACE,
        InterfaceTypeScope.EXTERNAL,
        InterfaceTypeScope.BUILTIN,
        InterfaceTypeScope.UNRESOLVED_LOCAL,
    ]
    assert uses.unresolved_types == ["Missing"]
    json.dumps(result.model_dump(mode="json"))


def test_single_interface_filter_accepts_suffix(
    tmp_path: Path, write_package: Callable[..., Path]
) -> None:
    package = write_package(tmp_path / "demo", name="demo")
    _interface(package, "msg/One.msg", "int32 value\n")
    _interface(package, "srv/One.srv", "---\n")

    result = inspect_interfaces(
        ServerSettings(root_path=tmp_path),
        relative_path="demo",
        interface_name="One.msg",
    )

    assert [(item.name, item.kind) for item in result.interfaces] == [("One", "msg")]


def test_interface_name_path_traversal_is_rejected(
    tmp_path: Path, write_package: Callable[..., Path]
) -> None:
    write_package(tmp_path / "demo", name="demo")

    result = inspect_interfaces(
        ServerSettings(root_path=tmp_path),
        package_name="demo",
        interface_name="../Secret.msg",
    )

    assert result.issues[0].code == "INVALID_INTERFACE_NAME"


def test_missing_interface_is_reported(tmp_path: Path, write_package: Callable[..., Path]) -> None:
    write_package(tmp_path / "demo", name="demo")

    result = inspect_interfaces(
        ServerSettings(root_path=tmp_path),
        package_name="demo",
        interface_name="Missing",
    )

    assert result.issues[0].code == "INTERFACE_NOT_FOUND"


def test_oversized_interface_is_not_read(
    tmp_path: Path, write_package: Callable[..., Path]
) -> None:
    package = write_package(tmp_path / "demo", name="demo")
    _interface(package, "msg/Huge.msg", "x" * (INTERFACE_MAX_BYTES + 1))

    result = inspect_interfaces(ServerSettings(root_path=tmp_path), package_name="demo")

    assert result.interfaces[0].issues[0].code == "INTERFACE_FILE_TOO_LARGE"
