from pathlib import Path

import pytest

from ros2_workspace_mcp.analyzers.launch import LAUNCH_MAX_BYTES, analyze_launch_file
from ros2_workspace_mcp.config import ServerSettings


def test_static_include_is_resolvable(tmp_path: Path) -> None:
    launch = tmp_path / "launch"
    launch.mkdir()
    (launch / "child.launch.py").write_text("LaunchDescription([])", encoding="utf-8")
    (launch / "main.launch.py").write_text(
        "IncludeLaunchDescription(PythonLaunchDescriptionSource('child.launch.py'))",
        encoding="utf-8",
    )

    result = analyze_launch_file(
        ServerSettings(root_path=tmp_path), relative_path="launch/main.launch.py"
    )

    assert result.valid
    assert result.includes[0].resolvable


@pytest.mark.parametrize("name", ["demo.launch.xml", "demo.launch.yaml", "demo.launch.yml"])
def test_supported_non_python_formats(tmp_path: Path, name: str) -> None:
    path = tmp_path / name
    content = "<launch/>" if name.endswith("xml") else "launch: []"
    path.write_text(content, encoding="utf-8")

    assert analyze_launch_file(ServerSettings(root_path=tmp_path), relative_path=name).valid


def test_unsupported_extension_and_path_escape(tmp_path: Path) -> None:
    settings = ServerSettings(root_path=tmp_path)

    unsupported = analyze_launch_file(settings, relative_path="launch.py")
    escaped = analyze_launch_file(settings, relative_path="../outside.launch.py")

    assert unsupported.issues[0].code == "UNSUPPORTED_LAUNCH_FORMAT"
    assert escaped.issues[0].code == "PATH_OUTSIDE_ROOT"


def test_oversized_launch_is_not_read(tmp_path: Path) -> None:
    path = tmp_path / "huge.launch.py"
    path.write_text("x" * (LAUNCH_MAX_BYTES + 1), encoding="utf-8")

    result = analyze_launch_file(ServerSettings(root_path=tmp_path), relative_path=path.name)

    assert result.issues[0].code == "LAUNCH_FILE_TOO_LARGE"


def test_external_file_symlink_is_rejected(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside.launch.py"
    outside.write_text("LaunchDescription([])", encoding="utf-8")
    link = root / "escape.launch.py"
    try:
        link.symlink_to(outside)
    except OSError as exc:
        pytest.skip(f"file symlinks unavailable on this platform: {exc}")

    result = analyze_launch_file(ServerSettings(root_path=root), relative_path="escape.launch.py")

    assert result.issues[0].code == "PATH_OUTSIDE_ROOT"
