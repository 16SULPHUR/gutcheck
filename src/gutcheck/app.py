import asyncio
import logging
import secrets
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Response
from pydantic import BaseModel, ValidationError

from gutcheck import __version__
from gutcheck.config import Settings, Thresholds, load_settings
from gutcheck.engine import Engine, LayaEngine
from gutcheck.policy import answer_probability, verdict
from gutcheck.store import AnswerRecord, DecisionRecord, DecisionStore

TRACE_HEADER = "X-Gutcheck-Trace-Id"

log = logging.getLogger("gutcheck")

State = str | dict[str, Any] | list[Any]


class SystemOneRequest(BaseModel):
    state: State
    questions: dict[str, dict[str, Any]]
    model: str | None = None


class DecideRequest(BaseModel):
    model_config = {"extra": "forbid"}

    state: State
    questions: dict[str, dict[str, Any]]
    model: str | None = None
    policy: Thresholds | None = None


class EngineStatus(BaseModel):
    backend: str
    loaded: list[str]


class Health(BaseModel):
    status: str
    version: str
    engine: EngineStatus


@dataclass
class Outcome:
    trace_id: str
    result: dict[str, Any]
    probabilities: dict[str, float]
    verdicts: dict[str, str] | None
    latency_ms: float


def _split_policies(
    questions: dict[str, dict[str, Any]], default: Thresholds
) -> tuple[dict[str, dict[str, Any]], dict[str, Thresholds]]:
    """Strip each question's optional `policy` and resolve its thresholds."""
    plain, thresholds = {}, {}
    for qid, q in questions.items():
        q = dict(q)
        raw = q.pop("policy", None)
        try:
            thresholds[qid] = default if raw is None else Thresholds.model_validate(raw)
        except ValidationError as e:
            raise HTTPException(422, f"question {qid!r}: invalid policy: {e}") from e
        plain[qid] = q
    return plain, thresholds


def _record(
    trace_id: str,
    endpoint: str,
    state: State,
    questions: dict[str, dict[str, Any]],
    result: dict[str, Any],
    probabilities: dict[str, float],
    verdicts: dict[str, str] | None,
    latency_ms: float,
) -> DecisionRecord:
    routing = result.get("routing") or {}
    return DecisionRecord(
        trace_id=trace_id,
        endpoint=endpoint,
        model=routing.get("model"),
        routing_reason=routing.get("reason"),
        latency_ms=latency_ms,
        state=state,
        answers=[
            AnswerRecord(
                question_id=qid,
                question=questions[qid],
                answer=a,
                answer_probability=probabilities[qid],
                verdict=verdicts[qid] if verdicts else None,
            )
            for qid, a in result.get("answers", {}).items()
        ],
    )


def create_app(
    settings: Settings | None = None,
    engine: Engine | None = None,
    store: DecisionStore | None = None,
) -> FastAPI:
    settings = settings or load_settings()
    engine = engine or LayaEngine(settings.engine)
    # one forward pass at a time; inference is blocking torch and must stay off the event loop
    pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="gutcheck-infer")

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        nonlocal store
        if store is None and settings.store.path:
            store = DecisionStore(settings.store.path, settings.store.save_state)
        engine.start()
        yield
        pool.shutdown(wait=True)
        engine.close()
        if store is not None:
            store.close()

    app = FastAPI(title="gutcheck", version=__version__, lifespan=lifespan)
    app.state.settings = settings

    def require_key(authorization: str | None = Header(default=None)) -> None:
        if settings.api_key is None:
            return
        expected = "Bearer " + settings.api_key.get_secret_value()
        if authorization is None or not secrets.compare_digest(
            authorization.encode(), expected.encode()
        ):
            raise HTTPException(401, "invalid or missing bearer token")

    def infer(
        endpoint: str,
        state: State,
        questions: dict[str, dict[str, Any]],
        model: str | None,
        thresholds: dict[str, Thresholds] | None,
    ) -> Outcome:
        start = time.perf_counter()
        result = engine.predict(state, questions, model)
        latency_ms = (time.perf_counter() - start) * 1000

        answers = result.get("answers", {})
        probabilities = {qid: answer_probability(a) for qid, a in answers.items()}
        verdicts = (
            {qid: verdict(p, thresholds[qid]) for qid, p in probabilities.items()}
            if thresholds is not None
            else None
        )
        trace_id = "gc_" + uuid.uuid4().hex
        if store is not None:
            try:
                store.record(
                    _record(
                        trace_id,
                        endpoint,
                        state,
                        questions,
                        result,
                        probabilities,
                        verdicts,
                        latency_ms,
                    )
                )
            except Exception:
                # a failed log write must not fail the decision
                log.exception("could not log decision %s", trace_id)
        return Outcome(trace_id, result, probabilities, verdicts, latency_ms)

    async def run(*args: Any) -> Outcome:
        try:
            return await asyncio.get_running_loop().run_in_executor(pool, infer, *args)
        except ValueError as e:
            # Laya raises ValueError for malformed questions
            raise HTTPException(422, str(e)) from e

    @app.get("/healthz", response_model=Health)
    def healthz() -> Health:
        return Health(
            status="ok",
            version=__version__,
            engine=EngineStatus(backend=engine.backend, loaded=engine.loaded()),
        )

    @app.post("/v1/systemone", dependencies=[Depends(require_key)])
    async def systemone(req: SystemOneRequest, response: Response) -> dict[str, Any]:
        """Jev-compatible passthrough: Laya's answers, unchanged."""
        out = await run("systemone", req.state, req.questions, req.model, None)
        response.headers[TRACE_HEADER] = out.trace_id
        return out.result

    @app.post("/v1/decide", dependencies=[Depends(require_key)])
    async def decide(req: DecideRequest, response: Response) -> dict[str, Any]:
        """Answers plus a verdict per question: act, review or escalate."""
        questions, thresholds = _split_policies(req.questions, req.policy or settings.policy)
        out = await run("decide", req.state, questions, req.model, thresholds)
        response.headers[TRACE_HEADER] = out.trace_id
        routing = out.result.get("routing")
        answers = {
            qid: {
                **a,
                "answer_probability": round(out.probabilities[qid], 4),
                "verdict": out.verdicts[qid],
            }
            for qid, a in out.result.get("answers", {}).items()
        }
        return {
            "trace_id": out.trace_id,
            "model": (routing or {}).get("model") or out.result.get("model"),
            "answers": answers,
            "routing": routing,
            "usage": out.result.get("usage"),
            "latency_ms": round(out.latency_ms, 1),
        }

    return app
