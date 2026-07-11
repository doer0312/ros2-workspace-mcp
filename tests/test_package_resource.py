import asyncio
import json
from collections.abc import Callable
from pathlib import Path

import pytest
from mcp.server.fastmcp.exceptions import ResourceError

import ros2_workspace_mcp.resources.package as package_resource_module
from ros2_workspace_mcp.config import ServerSettings
from ros2_workspace_mcp.resources.package import (
    PACKAGE_RESOURCE_MAX_JSON_BYTES,
    build_package_context,
    validate_package_name,
)
from ros2_workspace_mcp.server import create_server


def test_package_template_is_listed(tmp_path: Path) -> None:
    server = create_server(ServerSettings(root_path=tmp_path))

    templates = asyncio.run(server.list_resource_templates())

    assert len(templates) == 1
    assert templates[0].uriTemplate == "ros2-workspace://package/{package_name}"
    assert templates[0].name == "package-context"
    assert templates[0].mimeType == "application/json"


@pytest.mark.parametrize(
    "value",
    ["", "Demo", "with/slash", "with\\slash", ".", "..", "%2e%2e", "a" * 65],
)
def test_invalid_package_names_are_rejected(value: str) -> None:
    with pytest.raises(ResourceError):
        validate_package_name(value)


def test_missing_and_ambiguous_packages_use_resource_errors(
    tmp_path: Path, write_package: Callable[..., Path]
) -> None:
    settings = ServerSettings(root_path=tmp_path)
    with pytest.raises(ResourceError, match="PACKAGE_NOT_FOUND"):
        build_package_context(settings, "missing")

    write_package(tmp_path / "one", name="duplicate")
    write_package(tmp_path / "two", name="duplicate")
    with pytest.raises(ResourceError, match="AMBIGUOUS_PACKAGE_NAME") as exc_info:
        build_package_context(settings, "duplicate")

    assert "one" in str(exc_info.value)
    assert "two" in str(exc_info.value)


def test_package_context_is_compact_and_does_not_execute_setup(
    tmp_path: Path, write_package: Callable[..., Path]
) -> None:
    package = write_package(tmp_path / "demo", name="demo", build_type="ament_python")
    marker = tmp_path / "EXECUTED"
    (package / "setup.py").write_text(
        f"from pathlib import Path\nPath({str(marker)!r}).write_text('bad')\n",
        encoding="utf-8",
    )
    launch = package / "launch"
    launch.mkdir()
    (launch / "demo.launch.py").touch()

    text = build_package_context(ServerSettings(root_path=tmp_path), "demo")
    payload = json.loads(text)

    assert payload["name"] == "demo"
    assert payload["detailed_tool_hint"]["tool"] == "inspect_package"
    assert payload["launch_files"] == ["demo/launch/demo.launch.py"]
    assert not marker.exists()
    assert len(text.encode("utf-8")) <= PACKAGE_RESOURCE_MAX_JSON_BYTES
    assert "Path(" not in text


def test_package_context_marks_file_truncation(
    monkeypatch, tmp_path: Path, write_package: Callable[..., Path]
) -> None:
    package = write_package(tmp_path / "demo", name="demo")
    launch = package / "launch"
    launch.mkdir()
    for name in ("a.launch.py", "b.launch.py"):
        (launch / name).touch()
    monkeypatch.setattr(package_resource_module, "PACKAGE_RESOURCE_MAX_FILES_PER_KIND", 1)

    payload = json.loads(build_package_context(ServerSettings(root_path=tmp_path), "demo"))

    assert payload["truncated"]
    assert "launch_files_limit" in payload["truncation_reason"]
    assert len(payload["launch_files"]) == 1


def test_read_package_template_through_public_api(
    tmp_path: Path, write_package: Callable[..., Path]
) -> None:
    write_package(tmp_path / "demo", name="demo")
    server = create_server(ServerSettings(root_path=tmp_path))

    contents = list(asyncio.run(server.read_resource("ros2-workspace://package/demo")))

    assert contents[0].mime_type == "application/json"
    assert json.loads(contents[0].content)["name"] == "demo"
