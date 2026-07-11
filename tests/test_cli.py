from pathlib import Path
from unittest.mock import Mock

import pytest

from ros2_workspace_mcp import __main__, cli


def test_cli_requires_root(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc_info:
        cli.main([])

    assert exc_info.value.code != 0
    assert "--root" in capsys.readouterr().err


def test_cli_rejects_missing_path(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc_info:
        cli.main(["--root", str(tmp_path / "missing")])

    assert exc_info.value.code != 0
    assert "workspace root does not exist" in capsys.readouterr().err


def test_cli_starts_server_with_validated_settings(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    run_server = Mock()
    monkeypatch.setattr(cli, "run_server", run_server)

    assert cli.main(["--root", str(tmp_path)]) == 0
    settings = run_server.call_args.args[0]
    assert settings.root_path == tmp_path.resolve()


def test_module_entry_point_uses_cli_main(monkeypatch: pytest.MonkeyPatch) -> None:
    assert __main__.main is cli.main
