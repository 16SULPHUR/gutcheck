"""Runs a real Laya checkpoint. Downloads weights, so it only runs with RUN_LAYA_E2E=1."""

import os

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_LAYA_E2E") != "1", reason="set RUN_LAYA_E2E=1 to run against real Laya"
)


def test_decide_with_real_laya(tmp_path):
    from gutcheck.app import create_app
    from gutcheck.config import load_settings

    settings = load_settings(
        engine={"device": "cpu", "models": ["english"], "max_loaded": 1},
        store={"path": str(tmp_path / "gutcheck.db")},
    )
    questions = {
        "department": {
            "type": "choice",
            "instructions": "Which department should handle this?",
            "criteria": {"billing": "invoices, payments, refunds", "technical": "bugs, outages"},
        },
        "refund": {"type": "noul", "instructions": "Does the customer ask for money back?"},
        "frustration": {
            "type": "score",
            "instructions": "How frustrated does the customer sound?",
            "criteria": ["calm", "annoyed", "angry"],
        },
    }
    state = {"subject": "Charged twice", "body": "You billed me twice for March. Refund one now."}

    with TestClient(create_app(settings)) as client:
        assert client.get("/healthz").json()["engine"]["loaded"] == ["english"]
        r = client.post("/v1/decide", json={"state": state, "questions": questions})

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["model"] == "english"
    for qid, answer in body["answers"].items():
        assert answer["verdict"] in {"act", "review", "escalate"}, qid
        assert 0.0 <= answer["answer_probability"] <= 1.0
    choice = body["answers"]["department"]
    assert choice["choice"] in {"billing", "technical"}
    assert sum(choice["probabilities"].values()) == pytest.approx(1.0, abs=1e-3)
