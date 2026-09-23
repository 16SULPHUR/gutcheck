import pytest
from pydantic import ValidationError

from gutcheck.config import load_settings


def test_defaults():
    s = load_settings()
    assert (s.host, s.port, s.log_level) == ("127.0.0.1", 8080, "info")
    assert s.engine.models == ["english", "multilingual"]
    assert s.engine.max_loaded == 2


def test_yaml_file(tmp_path):
    cfg = tmp_path / "gutcheck.yaml"
    cfg.write_text("port: 9000\nengine:\n  device: cuda\n  models: [multilingual]\n")
    s = load_settings(cfg)
    assert s.port == 9000
    assert s.engine.device == "cuda"
    assert s.engine.models == ["multilingual"]


def test_config_path_from_env(tmp_path, monkeypatch):
    cfg = tmp_path / "gutcheck.yaml"
    cfg.write_text("port: 9001\n")
    monkeypatch.setenv("GUTCHECK_CONFIG", str(cfg))
    assert load_settings().port == 9001


def test_precedence(tmp_path, monkeypatch):
    cfg = tmp_path / "gutcheck.yaml"
    cfg.write_text("port: 9000\nhost: 0.0.0.0\nlog_level: debug\n")
    monkeypatch.setenv("GUTCHECK_PORT", "9100")
    monkeypatch.setenv("GUTCHECK_HOST", "10.0.0.1")
    s = load_settings(cfg, host="192.168.1.1")
    assert s.host == "192.168.1.1"
    assert s.port == 9100
    assert s.log_level == "debug"


def test_nested_env(monkeypatch):
    monkeypatch.setenv("GUTCHECK_ENGINE__DEVICE", "cpu")
    monkeypatch.setenv("GUTCHECK_ENGINE__MAX_LOADED", "1")
    s = load_settings()
    assert s.engine.device == "cpu"
    assert s.engine.max_loaded == 1


def test_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_settings(tmp_path / "nope.yaml")


@pytest.mark.parametrize(
    "body",
    ["prot: 9000\n", "engine:\n  models: [klingon]\n", "engine:\n  max_loaded: 5\n"],
)
def test_invalid_yaml_rejected(tmp_path, body):
    cfg = tmp_path / "gutcheck.yaml"
    cfg.write_text(body)
    with pytest.raises(ValidationError):
        load_settings(cfg)
