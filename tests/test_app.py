from fastapi.testclient import TestClient

from gutcheck import __version__
from gutcheck.app import create_app
from gutcheck.config import load_settings


def test_healthz():
    client = TestClient(create_app(load_settings()))
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {
        "status": "ok",
        "version": __version__,
        "engine": {"backend": "laya", "loaded": False, "models": ["english", "multilingual"]},
    }


def test_healthz_reports_configured_models():
    app = create_app(load_settings(engine={"models": ["typed-decisions"]}))
    body = TestClient(app).get("/healthz").json()
    assert body["engine"]["models"] == ["typed-decisions"]
