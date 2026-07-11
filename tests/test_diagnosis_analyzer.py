import json
from collections.abc import Callable
from pathlib import Path

import ros2_workspace_mcp.analyzers.diagnosis as diagnosis_module
from ros2_workspace_mcp.analyzers.diagnosis import _deduplicate, diagnose_workspace
from ros2_workspace_mcp.config import ServerSettings
from ros2_workspace_mcp.models.common import ScanIssue, Severity


def _append_manifest(package: Path, text: str) -> None:
    manifest = package / "package.xml"
    content = manifest.read_text(encoding="utf-8")
    manifest.write_text(content.replace("</package>", f"{text}</package>"), encoding="utf-8")


def test_complete_small_workspace(tmp_path: Path, write_package: Callable[..., Path]) -> None:
    interfaces = write_package(
        tmp_path / "src" / "demo_interfaces",
        name="demo_interfaces",
        build_type="ament_cmake",
    )
    python_package = write_package(
        tmp_path / "src" / "demo_python",
        name="demo_python",
        build_type="ament_python",
    )
    robot = write_package(
        tmp_path / "src" / "demo_robot",
        name="demo_robot",
        build_type="ament_cmake",
    )
    (interfaces / "CMakeLists.txt").touch()
    message = interfaces / "msg" / "State.msg"
    message.parent.mkdir()
    message.write_text("int32 state\n", encoding="utf-8")
    (python_package / "setup.py").write_text(
        "from setuptools import setup\nsetup()", encoding="utf-8"
    )
    _append_manifest(python_package, "<depend>demo_interfaces</depend>")
    launch = python_package / "launch" / "demo.launch.py"
    launch.parent.mkdir()
    launch.write_text("Node(package='demo_python', executable='node')", encoding="utf-8")
    (robot / "CMakeLists.txt").touch()
    urdf = robot / "urdf" / "robot.urdf"
    urdf.parent.mkdir()
    urdf.write_text('<robot name="demo"><link name="base"/></robot>', encoding="utf-8")

    result = diagnose_workspace(ServerSettings(root_path=tmp_path))

    assert result.status == "ok"
    assert result.package_summary.analyzed_count == 3
    assert result.dependency_summary["edge_count"] == 1
    assert result.interface_summary.valid_count == 1
    assert result.launch_summary.valid_count == 1
    assert result.robot_description_summary.valid_count == 1
    assert not result.limits_reached
    assert len(json.dumps(result.model_dump(mode="json"))) < 50_000


def test_mixed_error_sets_status_and_does_not_stop_other_files(
    tmp_path: Path, write_package: Callable[..., Path]
) -> None:
    package = write_package(tmp_path / "demo", name="demo", build_type="ament_python")
    (package / "setup.py").touch()
    launch = package / "launch"
    launch.mkdir()
    (launch / "bad.launch.py").write_text("def broken(", encoding="utf-8")
    (launch / "good.launch.xml").write_text("<launch/>", encoding="utf-8")

    result = diagnose_workspace(ServerSettings(root_path=tmp_path))

    assert result.status == "error"
    assert result.launch_summary.analyzed_count == 2
    assert result.launch_summary.valid_count == 1
    assert result.launch_summary.invalid_count == 1
    assert result.severity_counts["ERROR"] >= 1


def test_issue_deduplication_uses_stable_key() -> None:
    issue = ScanIssue(
        severity=Severity.WARNING,
        code="SAME",
        message="same",
        path="file",
        package_name="pkg",
        line=1,
    )
    different_line = issue.model_copy(update={"line": 2})

    result = _deduplicate([issue, issue.model_copy(), different_line])

    assert len(result) == 2


def test_package_limit_is_reported(
    monkeypatch, tmp_path: Path, write_package: Callable[..., Path]
) -> None:
    write_package(tmp_path / "one", name="one")
    write_package(tmp_path / "two", name="two")
    monkeypatch.setattr(diagnosis_module, "MAX_DIAGNOSIS_PACKAGES", 1)

    result = diagnose_workspace(ServerSettings(root_path=tmp_path))

    assert result.limits_reached
    assert result.package_summary.analyzed_count == 1
    assert len(result.skipped_files) == 1
    assert any(issue.code == "ANALYSIS_LIMIT_REACHED" for issue in result.issues)


def test_empty_workspace_is_warning_not_exception(tmp_path: Path) -> None:
    result = diagnose_workspace(ServerSettings(root_path=tmp_path))

    assert result.status == "warning"
    assert result.workspace_summary["package_count"] == 0
    assert any(issue.code == "NO_ROS_PACKAGES_FOUND" for issue in result.issues)
