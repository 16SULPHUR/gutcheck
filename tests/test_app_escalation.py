import time

import pytest
from fastapi.testclient import TestClient

from gutcheck.app import create_app
from gutcheck.config import load_settings

URGENT = {"urgent": {"type": "noul", "instructions": "Is this urgent?"}}
DEPT = {
    "department": {
        "type": "choice",
        "instructions": "Which department?",
        "criteria": {"billing": "money", "technical": "bugs"},
    }
}


class Chat:
    model = "fake-llm"

    def __init__(self, answer="true", error=None):
        self.answer, self.error, self.calls = answer, error, []

    def complete(self, messages):
        self.calls.append(messages)
        if self.error:
            raise self.error
        return f'{{"answer": "{self.answer}"}}'


@pytest.fixture
def make(engine, agents, tmp_path):
    def build(chat, mode="live", probs=None, **escalation):
        agents["english"].probs.update(probs or {"urgent": 0.55, "department": 0.7})
        settings = load_settings(
            escalation={"mode": mode, "model": "fake-llm", **escalation},
            store={"path": str(tmp_path / "g.db")},
        )
        return TestClient(create_app(settings, engine=engine, chat=chat))

    return build


def decide(client, questions=None, **extra):
    body = {"state": "hello", "questions": questions or {**URGENT, **DEPT}, **extra}
    r = client.post("/v1/decide", json=body)
    assert r.status_code == 200, r.text
    return r.json()


def test_off_never_calls_the_llm(client, agents):
    agents["english"].probs["urgent"] = 0.55
    out = decide(client, URGENT)
    assert out["answers"]["urgent"]["verdict"] == "escalate"
    assert "escalation" not in out["answers"]["urgent"]


def test_live_adds_a_second_opinion_to_escalated_answers_only(make):
    chat = Chat("false")
    with make(chat) as client:
        out = decide(client)
    urgent, dept = out["answers"]["urgent"], out["answers"]["department"]
    assert urgent["verdict"] == "escalate"
    assert urgent["noul"] == 0.55
    assert urgent["escalation"]["model"] == "fake-llm"
    assert urgent["escalation"]["answer"] == "false"
    assert urgent["escalation"]["agrees"] is False
    assert dept["verdict"] == "review" and "escalation" not in dept
    assert len(chat.calls) == 1


def test_verdicts_can_include_review(make):
    chat = Chat("billing")
    with make(chat, verdicts=["review", "escalate"]) as client:
        out = decide(client)
    assert out["answers"]["department"]["escalation"]["agrees"] is True
    assert len(chat.calls) == 2


def test_confident_answers_are_not_escalated(make):
    chat = Chat()
    with make(chat, probs={"urgent": 0.99}) as client:
        out = decide(client, URGENT)
    assert out["answers"]["urgent"]["verdict"] == "act"
    assert chat.calls == []


def test_an_unreachable_llm_keeps_laya_answer_and_hides_the_details(make):
    chat = Chat(error=ConnectionError("http://10.0.0.5:11434 refused"))
    with make(chat) as client:
        out = decide(client, URGENT)
    esc = out["answers"]["urgent"]["escalation"]
    assert esc["error"] == "ConnectionError" and "answer" not in esc
    assert out["answers"]["urgent"]["verdict"] == "escalate"
    assert "10.0.0.5" not in str(out)


def test_shadow_answers_immediately_and_only_logs(make):
    chat = Chat("false")
    with make(chat, mode="shadow") as client:
        out = decide(client, URGENT)
        assert "escalation" not in out["answers"]["urgent"]
        for _ in range(100):
            stats = client.get("/v1/stats").json()["questions"][0]["escalation"]
            if stats:
                break
            time.sleep(0.05)
    assert stats == {"asked": 1, "agree": 0, "disagree": 1, "errors": 0}
    assert len(chat.calls) == 1


def test_stats_compare_laya_and_the_llm_once_labelled(make):
    # Laya leans true (0.55) and the LLM always says false
    with make(Chat("false")) as client:
        for truth in (True, True, True, False):
            trace = decide(client, URGENT)["trace_id"]
            client.post(
                "/v1/feedback",
                json={"trace_id": trace, "answers": {"urgent": {"answer": truth}}},
            )
        stats = client.get("/v1/stats").json()["questions"][0]["escalation"]
    assert stats == {
        "asked": 4,
        "agree": 0,
        "disagree": 4,
        "errors": 0,
        "labelled": 4,
        "laya_correct": 3,
        "llm_correct": 1,
    }


def test_metrics_count_outcomes(make):
    with make(Chat("false")) as client:
        decide(client, URGENT)
        text = client.get("/metrics").text
    assert 'gutcheck_escalations_total{outcome="disagree",question="inline"} 1.0' in text


def test_systemone_is_never_escalated(make):
    chat = Chat()
    with make(chat) as client:
        r = client.post("/v1/systemone", json={"state": "x", "questions": URGENT})
    assert r.status_code == 200 and chat.calls == []
