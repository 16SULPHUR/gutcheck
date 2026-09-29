import os

import pytest
from fastapi.testclient import TestClient
from laya.router import Router

from gutcheck.app import create_app
from gutcheck.config import load_settings
from gutcheck.engine import LayaEngine


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for key in list(os.environ):
        if key.startswith("GUTCHECK_"):
            monkeypatch.delenv(key)


class FakeAgent:
    """Stands in for a Laya checkpoint: same call shape and Jev-style output, no torch.

    The top option of each question gets probability `probs.get(qid, 0.95)`.
    """

    def __init__(self, probs: dict[str, float] | None = None):
        self.probs = probs if probs is not None else {}
        self.calls: list[tuple] = []

    def system_one(self, state, questions):
        self.calls.append((state, questions))
        answers = {}
        for qid, q in questions.items():
            if "instructions" not in q:
                raise ValueError(f"question {qid!r}: no 'instructions'")
            answers[qid] = self._answer(q, self.probs.get(qid, 0.95))
        return {
            "model": "laya-rl-agent",
            "answers": answers,
            "usage": {"input_tokens": 12 * len(questions), "output_tokens": 0},
        }

    @staticmethod
    def _answer(q, p):
        if q["type"] == "noul":
            return {"type": "noul", "noul": p, "confidence": max(p, 1 - p)}
        crit = q["criteria"]
        labels = list(crit) if q["type"] == "choice" else [str(i) for i in range(len(crit))]
        rest = (1 - p) / (len(labels) - 1) if len(labels) > 1 else 0.0
        probs = {label: (p if i == 0 else rest) for i, label in enumerate(labels)}
        if len(labels) == 1:
            probs = {labels[0]: 1.0}
        if q["type"] == "choice":
            return {"type": "choice", "choice": labels[0], "probabilities": probs, "confidence": p}
        return {
            "type": "score",
            "score": sum(int(k) * v for k, v in probs.items()),
            "legend": {str(i): c for i, c in enumerate(crit)},
            "probabilities": probs,
            "confidence": p,
        }


@pytest.fixture
def agents():
    return {"english": FakeAgent(), "multilingual": FakeAgent()}


@pytest.fixture
def engine(agents, monkeypatch):
    import huggingface_hub

    router = Router()
    for name, agent in agents.items():
        router.attach(name, agent)
    # bundled packs with their own checkpoint are answered by the fake english agent
    monkeypatch.setattr(huggingface_hub, "snapshot_download", lambda *a, **k: "unused")
    settings = load_settings()
    return LayaEngine(settings.engine, router=router, agent_factory=lambda p, s: agents["english"])


@pytest.fixture
def make_client(engine, tmp_path):
    def make(**overrides):
        overrides.setdefault("store", {"path": str(tmp_path / "gutcheck.db")})
        app = create_app(load_settings(**overrides), engine=engine)
        return TestClient(app)

    return make


@pytest.fixture
def client(make_client):
    with make_client() as c:
        yield c
