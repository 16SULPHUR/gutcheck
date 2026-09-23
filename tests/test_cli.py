import json

import pytest

from gutcheck import __version__
from gutcheck.cli import main


def test_version(capsys):
    with pytest.raises(SystemExit) as e:
        main(["--version"])
    assert e.value.code == 0
    assert __version__ in capsys.readouterr().out


def test_config_prints_resolved_settings(tmp_path, capsys):
    cfg = tmp_path / "gutcheck.yaml"
    cfg.write_text("port: 9000\n")
    assert main(["config", "--config", str(cfg)]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["port"] == 9000
    assert out["engine"]["max_loaded"] == 2


def test_missing_config_exits_2(tmp_path, capsys):
    assert main(["config", "--config", str(tmp_path / "nope.yaml")]) == 2
    assert "config file not found" in capsys.readouterr().err


def test_serve_passes_overrides_to_uvicorn(monkeypatch):
    import uvicorn

    seen = {}
    monkeypatch.setattr(uvicorn, "run", lambda app, **kw: seen.update(kw))
    assert main(["serve", "--port", "9123", "--host", "0.0.0.0"]) == 0
    assert seen == {"host": "0.0.0.0", "port": 9123, "log_level": "info"}
