import pytest
from fastapi.testclient import TestClient

from gutcheck.app import create_app
from gutcheck.config import load_settings
from space.guard import Guard, protect

SITE = "https://gutcheck-blush.vercel.app"
QUESTION = {"urgent": {"type": "noul", "instructions": "Is this urgent?"}}


@pytest.fixture
def public(engine):
    settings = load_settings()
    settings.store.path = None
    app = protect(create_app(settings, engine=engine), origins=[SITE])
    with TestClient(app) as c:
        yield c


def test_decide_works_with_cors(public):
    r = public.post(
        "/v1/decide",
        json={"state": "hello", "questions": QUESTION},
        headers={"Origin": SITE},
    )
    assert r.status_code == 200
    assert r.json()["answers"]["urgent"]["verdict"] == "act"
    assert r.headers["access-control-allow-origin"] == SITE


def test_other_origin_gets_no_cors_header(public):
    r = public.post(
        "/v1/decide",
        json={"state": "hello", "questions": QUESTION},
        headers={"Origin": "https://evil.example"},
    )
    assert "access-control-allow-origin" not in r.headers


def test_preflight(public):
    r = public.options(
        "/v1/decide",
        headers={
            "Origin": SITE,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert r.status_code == 200
    assert r.headers["access-control-allow-origin"] == SITE


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("post", "/v1/feedback"),
        ("post", "/v1/calibrate"),
        ("post", "/v1/systemone"),
        ("get", "/v1/stats"),
        ("get", "/metrics"),
        ("get", "/dashboard"),
        ("get", "/docs"),
        ("get", "/openapi.json"),
    ],
)
def test_everything_else_is_closed(public, method, path):
    assert getattr(public, method)(path).status_code == 404


def test_read_only_routes_stay_open(public):
    assert public.get("/healthz").status_code == 200
    assert public.get("/v1/packs").status_code == 200


def test_input_limits(public):
    too_long = public.post("/v1/decide", json={"state": "x" * 3000, "questions": QUESTION})
    assert too_long.status_code == 422
    many = {f"q{i}": QUESTION["urgent"] for i in range(7)}
    assert public.post("/v1/decide", json={"state": "hi", "questions": many}).status_code == 422
    assert public.post("/v1/decide", content=b"not json").status_code == 422
    assert public.post("/v1/decide", content=b"x" * 20_000).status_code == 413


def test_rate_limit(engine):
    app = create_app(load_settings(), engine=engine)
    app.add_middleware(Guard, rate_limit=3, window=60)
    with TestClient(app) as c:
        codes = [
            c.post("/v1/decide", json={"state": "hi", "questions": QUESTION}).status_code
            for _ in range(5)
        ]
    assert codes == [200, 200, 200, 429, 429]
