import pytest
from fastapi.testclient import TestClient
from laya.router import Router

from gutcheck import evals
from gutcheck.app import create_app
from gutcheck.config import Thresholds, load_settings
from gutcheck.engine import LayaEngine
from gutcheck.packs import load_packs
from tests.conftest import FakeAgent
from tests.packs import TOY_PACK, write_toy_pack


@pytest.fixture
def setup(tmp_path, agents):
    d = write_toy_pack(
        tmp_path / "packs", TOY_PACK.replace("questions:", "model: {repo: ckpt}\nquestions:")
    )
    (d / "ckpt").mkdir()
    tuned = FakeAgent({"q": 0.7, "toy.bad": 0.7})
    built = []

    def factory(path, subfolder):
        built.append((path, subfolder))
        return tuned

    router = Router()
    for name, agent in agents.items():
        router.attach(name, agent)
    settings = load_settings(
        store={"path": str(tmp_path / "g.db")}, packs={"dirs": [str(tmp_path / "packs")]}
    )
    engine = LayaEngine(settings.engine, router=router, agent_factory=factory)
    return settings, engine, tuned, built, d


def test_pack_questions_run_on_the_pack_checkpoint(setup, agents):
    settings, engine, tuned, built, d = setup
    with TestClient(create_app(settings, engine=engine)) as c:
        questions = {"urgent": {"type": "noul", "instructions": "Is this urgent?"}}
        r = c.post("/v1/decide", json={"state": "hi", "questions": questions, "packs": ["toy"]})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["answers"]["toy.bad"]["model"] == "toy@2"
        assert body["answers"]["toy.bad"]["noul"] == 0.7
        assert "model" not in body["answers"]["urgent"]
        assert body["model"] == "english"
        assert body["usage"]["input_tokens"] == 24
        assert built == [(str(d / "ckpt"), None)]
        assert list(tuned.calls[0][1]) == ["toy.bad"]
        assert list(agents["english"].calls[0][1]) == ["urgent"]
        assert "toy@2" in c.get("/healthz").json()["engine"]["loaded"]
        packs = {p["id"]: p for p in c.get("/v1/packs").json()["packs"]}
        assert packs["toy"]["model"] == {"repo": "ckpt", "revision": "main", "subfolder": None}

        only_pack = c.post("/v1/decide", json={"state": "hi", "questions": {}, "packs": ["toy"]})
        assert only_pack.json()["model"] == "toy@2"
        assert len(agents["english"].calls) == 1


def test_eval_uses_the_pack_checkpoint(setup):
    settings, engine, tuned, built, d = setup
    pack = load_packs(settings.packs.dirs)["toy"]
    report = evals.evaluate_pack(engine, pack, Thresholds(), log=lambda _: None)
    assert report["questions"]["bad"]["models"] == {"toy@2": 18}
    assert len(tuned.calls) == 18


def test_remote_checkpoint_is_downloaded_pinned(monkeypatch, tmp_path):
    import huggingface_hub

    seen = {}

    def fake_download(repo, revision, allow_patterns):
        seen.update(repo=repo, revision=revision, patterns=allow_patterns)
        return str(tmp_path)

    monkeypatch.setattr(huggingface_hub, "snapshot_download", fake_download)
    engine = LayaEngine(
        load_settings().engine, router=Router(), agent_factory=lambda p, s: FakeAgent()
    )
    engine.add_checkpoint("pg@2", "someone/laya-prompt-guard", "abc123", "english")
    r = engine.predict("hi", {"q": {"type": "noul", "instructions": "?"}}, "pg@2")
    assert r["routing"] == {"model": "pg@2", "reason": "pack checkpoint"}
    assert seen["repo"] == "someone/laya-prompt-guard"
    assert seen["revision"] == "abc123"
    assert "english/model.safetensors" in seen["patterns"]


def test_model_repo_dataset_url(monkeypatch, tmp_path):
    from gutcheck.packs import DatasetSpec

    urls = []

    class Resp:
        headers = {}

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

        def read(self):
            return b"text,label\\n"

    def fake_open(url, timeout):
        urls.append(url)
        return Resp()

    monkeypatch.setattr(evals.urllib.request, "urlopen", fake_open)
    spec = DatasetSpec(
        repo="me/ckpt", repo_type="model", revision="r1", path="heldout/a.csv", license="x"
    )
    evals.fetch(spec, tmp_path, cache_dir=tmp_path)
    assert urls == ["https://huggingface.co/me/ckpt/resolve/r1/heldout/a.csv"]
