import sqlite3

from gutcheck import __version__
from gutcheck.app import TRACE_HEADER

TICKET = {"subject": "Duplicate charge on invoice #4411", "body": "We were billed twice."}
QUESTIONS = {
    "department": {
        "type": "choice",
        "instructions": "Which department should handle this?",
        "criteria": {"billing": "invoices, refunds", "technical": "bugs, outages"},
    },
    "urgent": {"type": "noul", "instructions": "Is this urgent?"},
    "frustration": {
        "type": "score",
        "instructions": "How frustrated is the customer?",
        "criteria": ["calm", "annoyed", "angry"],
    },
}


def test_healthz(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {
        "status": "ok",
        "version": __version__,
        "engine": {"backend": "laya", "loaded": ["english", "multilingual"]},
    }


def test_systemone_passes_laya_answers_through(client, agents):
    r = client.post("/v1/systemone", json={"state": TICKET, "questions": QUESTIONS})
    assert r.status_code == 200
    body = r.json()
    assert body["model"] == "laya-rl-agent"
    assert body["answers"]["department"]["choice"] == "billing"
    assert body["answers"]["urgent"] == {"type": "noul", "noul": 0.95, "confidence": 0.95}
    assert "verdict" not in body["answers"]["urgent"]
    assert body["routing"]["model"] == "english"
    assert r.headers[TRACE_HEADER].startswith("gc_")
    assert agents["english"].calls == [(TICKET, QUESTIONS)]


def test_non_latin_state_routes_to_multilingual(client, agents):
    state = "मुझसे दो बार शुल्क लिया गया है, कृपया पैसे वापस करें"
    r = client.post("/v1/decide", json={"state": state, "questions": QUESTIONS})
    assert r.json()["model"] == "multilingual"
    assert len(agents["multilingual"].calls) == 1
    assert agents["english"].calls == []


def test_explicit_model_is_honoured_and_jev_ids_auto_route(client, agents):
    for model in ("multilingual", "jev-latest"):
        body = {"state": "hello there", "questions": QUESTIONS, "model": model}
        assert client.post("/v1/systemone", json=body).status_code == 200
    assert len(agents["multilingual"].calls) == 1
    assert len(agents["english"].calls) == 1


def test_decide_returns_verdicts(client, agents):
    agents["english"].probs.update({"department": 0.95, "urgent": 0.3, "frustration": 0.5})
    r = client.post("/v1/decide", json={"state": TICKET, "questions": QUESTIONS})
    assert r.status_code == 200
    body = r.json()
    assert body["trace_id"] == r.headers[TRACE_HEADER]
    assert body["model"] == "english"
    answers = body["answers"]
    assert (answers["department"]["verdict"], answers["department"]["answer_probability"]) == (
        "act",
        0.95,
    )
    # noul 0.3 means "no" with probability 0.7
    assert (answers["urgent"]["verdict"], answers["urgent"]["answer_probability"]) == (
        "review",
        0.7,
    )
    assert answers["frustration"]["verdict"] == "escalate"
    assert body["usage"] == {"input_tokens": 36, "output_tokens": 0}
    assert body["latency_ms"] >= 0


def test_request_and_question_policies(client, agents):
    agents["english"].probs.update({"department": 0.8, "urgent": 0.8})
    questions = {
        "department": QUESTIONS["department"],
        "urgent": {**QUESTIONS["urgent"], "policy": {"act_at": 0.99, "review_at": 0.9}},
    }
    r = client.post(
        "/v1/decide",
        json={"state": TICKET, "questions": questions, "policy": {"act_at": 0.75}},
    )
    answers = r.json()["answers"]
    assert answers["department"]["verdict"] == "act"
    assert answers["urgent"]["verdict"] == "escalate"
    # the policy key never reaches the model
    assert "policy" not in agents["english"].calls[0][1]["urgent"]


def test_invalid_policy_is_rejected(client):
    bad_q = {"urgent": {**QUESTIONS["urgent"], "policy": {"act_at": 0.5, "review_at": 0.8}}}
    r = client.post("/v1/decide", json={"state": "hi", "questions": bad_q})
    assert r.status_code == 422
    assert "urgent" in r.json()["detail"]

    r = client.post(
        "/v1/decide", json={"state": "hi", "questions": QUESTIONS, "policy": {"act_at": 2}}
    )
    assert r.status_code == 422


def test_decide_rejects_unknown_fields(client):
    r = client.post("/v1/decide", json={"state": "hi", "questions": QUESTIONS, "packs": ["x"]})
    assert r.status_code == 422


def test_malformed_question_is_422(client):
    r = client.post("/v1/decide", json={"state": "hi", "questions": {"q": {"type": "noul"}}})
    assert r.status_code == 422
    assert "instructions" in r.json()["detail"]


def test_empty_questions(client):
    r = client.post("/v1/decide", json={"state": "hi", "questions": {}})
    assert r.status_code == 200
    assert r.json()["answers"] == {}


def test_api_key(make_client):
    with make_client(api_key="s3cret") as c:
        body = {"state": "hi", "questions": QUESTIONS}
        assert c.post("/v1/decide", json=body).status_code == 401
        wrong = {"Authorization": "Bearer nope"}
        assert c.post("/v1/systemone", json=body, headers=wrong).status_code == 401
        right = {"Authorization": "Bearer s3cret"}
        assert c.post("/v1/decide", json=body, headers=right).status_code == 200
        assert c.get("/healthz").status_code == 200


def test_decisions_are_logged(client, tmp_path, agents):
    agents["english"].probs["urgent"] = 0.3
    r = client.post("/v1/decide", json={"state": TICKET, "questions": QUESTIONS})
    trace = r.json()["trace_id"]
    client.post("/v1/systemone", json={"state": "hello", "questions": QUESTIONS})

    db = sqlite3.connect(tmp_path / "gutcheck.db")
    rows = db.execute("SELECT trace_id, endpoint, model, state FROM decisions").fetchall()
    assert len(rows) == 2
    assert rows[0][:3] == (trace, "decide", "english")
    assert "invoice #4411" in rows[0][3]
    urgent = db.execute(
        "SELECT type, answer, answer_probability, verdict FROM answers"
        " WHERE trace_id = ? AND question_id = 'urgent'",
        (trace,),
    ).fetchone()
    assert urgent == ("noul", "0.3", 0.7, "review")
    passthrough = db.execute("SELECT verdict FROM answers WHERE trace_id != ?", (trace,)).fetchall()
    assert passthrough == [(None,)] * 3


def test_logging_can_be_disabled(make_client, tmp_path):
    with make_client(store={"path": None}) as c:
        assert c.post("/v1/decide", json={"state": "hi", "questions": QUESTIONS}).status_code == 200
    assert not (tmp_path / "gutcheck.db").exists()


def test_log_failure_does_not_fail_the_decision(engine):
    from fastapi.testclient import TestClient

    from gutcheck.app import create_app
    from gutcheck.config import load_settings

    class BrokenStore:
        def record(self, rec):
            raise OSError("disk full")

        def close(self):
            pass

    app = create_app(load_settings(), engine=engine, store=BrokenStore())
    with TestClient(app) as c:
        r = c.post("/v1/decide", json={"state": "hi", "questions": QUESTIONS})
    assert r.status_code == 200
