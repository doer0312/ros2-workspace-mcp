import asyncio
import json
from collections.abc import Callable
from pathlib import Path
from unittest.mock import Mock

import ros2_workspace_mcp.resources.workspace as workspace_resource_module
from ros2_workspace_mcp.config import ServerSettings
from ros2_workspace_mcp.resources.workspace import build_workspace_summary
from ros2_workspace_mcp.server import create_server


def test_fixed_resource_is_listed_with_json_mime(tmp_path: Path) -> None:
    server = create_server(ServerSettings(root_path=tmp_path))

    resources = asyncio.run(server.list_resources())

    assert len(resources) == 1
    assert str(resources[0].uri) == "ros2-workspace://summary"
    assert resources[0].name == "workspace-summary"
    assert resources[0].mimeType == "application/json"


def test_workspace_summary_is_stable_compact_json(
    tmp_path: Path, write_package: Callable[..., Path]
) -> None:
    package = write_package(tmp_path / "src" / "demo", name="demo")
    manifest = package / "package.xml"
    manifest.write_text(
        manifest.read_text(encoding="utf-8").replace(
            "A demo package", "SECRET RAW MANIFEST CONTENT"
        ),
        encoding="utf-8",
    )
    settings = ServerSettings(root_path=tmp_path)

    first = build_workspace_summary(settings)
    second = build_workspace_summary(settings)
    payload = json.loads(first)

    assert first == second
    assert payload["package_count"] == 1
    assert payload["packages"][0]["relative_path"] == "src/demo"
    assert "SECRET RAW MANIFEST CONTENT" not in first
    assert "<package" not in first


def test_empty_and_broken_workspace_are_readable(tmp_path: Path) -> None:
    empty = json.loads(build_workspace_summary(ServerSettings(root_path=tmp_path)))
    broken = tmp_path / "broken"
    broken.mkdir()
    (broken / "package.xml").write_text("<package>", encoding="utf-8")

    damaged = json.loads(build_workspace_summary(ServerSettings(root_path=tmp_path)))

    assert empty["package_count"] == 0
    assert damaged["invalid_package_count"] == 1
    assert any(issue["code"] == "INVALID_PACKAGE_XML" for issue in damaged["issues"])


def test_workspace_resource_reports_package_and_issue_truncation(
    monkeypatch, tmp_path: Path, write_package: Callable[..., Path]
) -> None:
    write_package(tmp_path / "one", name="duplicate")
    write_package(tmp_path / "two", name="duplicate")
    monkeypatch.setattr(workspace_resource_module, "WORKSPACE_RESOURCE_MAX_PACKAGES", 1)
    monkeypatch.setattr(workspace_resource_module, "WORKSPACE_RESOURCE_MAX_ISSUES", 1)

    payload = json.loads(build_workspace_summary(ServerSettings(root_path=tmp_path)))

    assert payload["truncated"]
    assert set(payload["truncation_reason"]) == {"package_limit", "issue_limit"}
    assert payload["original_package_count"] == 2
    assert len(payload["packages"]) == 1
    assert len(payload["issues"]) == 1


def test_server_creation_does_not_scan(monkeypatch, tmp_path: Path) -> None:
    analyze = Mock()
    monkeypatch.setattr(workspace_resource_module, "analyze_workspace", analyze)

    create_server(ServerSettings(root_path=tmp_path))

    analyze.assert_not_called()
