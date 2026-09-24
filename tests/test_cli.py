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


def test_packs_lists_bundled_packs(capsys):
    assert main(["packs"]) == 0
    out = capsys.readouterr().out
    assert "prompt-guard@1" in out
    assert "prompt-guard.injection [noul]" in out


def test_eval_writes_outputs_and_checks(tmp_path, monkeypatch, capsys):
    import gutcheck.engine
    from tests.packs import ToyEngine, write_toy_pack

    monkeypatch.setattr(gutcheck.engine, "LayaEngine", lambda cfg: ToyEngine())
    d = write_toy_pack(tmp_path / "packs")
    cfg = tmp_path / "gutcheck.yaml"
    cfg.write_text(f"packs:\n  dirs: [{tmp_path / 'packs'}]\n")
    summary = tmp_path / "summary.md"
    args = ["eval", "toy", "--config", str(cfg), "--check", "--summary", str(summary)]

    # no baseline yet: temperatures are fitted, and --check fails
    assert main([*args, "--write"]) == 1
    assert "no committed baseline" in capsys.readouterr().err
    assert (d / "eval.json").exists() and (d / "calibration.json").exists()
    assert "<code>toy/calibration.json</code>" in summary.read_text()

    assert main(args) == 0
    assert "within tolerance" in summary.read_text()
    assert "<code>toy/calibration.json</code>" not in summary.read_text()


def test_eval_unknown_pack(capsys):
    assert main(["eval", "nope"]) == 2
    assert "unknown pack" in capsys.readouterr().err
