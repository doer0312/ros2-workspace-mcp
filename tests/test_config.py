from pathlib import Path

import pytest
from pydantic import ValidationError

from ros2_workspace_mcp.config import ServerSettings


def test_valid_directory_creates_settings(tmp_path: Path) -> None:
    settings = ServerSettings(root_path=tmp_path)

    assert settings.root_path == tmp_path.resolve()
    assert settings.server_name == "ros2-workspace-inspector"
    assert settings.server_version == "0.1.0"


def test_relative_path_is_resolved(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.chdir(tmp_path)

    settings = ServerSettings(root_path=Path("workspace"))

    assert settings.root_path == workspace.resolve()
    assert settings.root_path.is_absolute()


def test_missing_path_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValidationError, match="workspace root does not exist"):
        ServerSettings(root_path=tmp_path / "missing")


def test_file_path_is_rejected(tmp_path: Path) -> None:
    file_path = tmp_path / "package.xml"
    file_path.write_text("<package/>", encoding="utf-8")

    with pytest.raises(ValidationError, match="workspace root is not a directory"):
        ServerSettings(root_path=file_path)


def test_settings_are_immutable(tmp_path: Path) -> None:
    settings = ServerSettings(root_path=tmp_path)

    with pytest.raises(ValidationError):
        settings.server_name = "changed"
