import asyncio
import logging
import secrets
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from importlib import resources
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Response
from fastapi.responses import HTMLResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from pydantic import BaseModel, Field, ValidationError, model_validator

from gutcheck import __version__
from gutcheck.calibration import apply_temperature, distribution
from gutcheck.config import Settings, Thresholds, load_settings
from gutcheck.engine import Engine, LayaEngine
from gutcheck.feedback import fingerprint, options, recalibrate, resolve
from gutcheck.metrics import Metrics
from gutcheck.packs import Pack, PackError, load_packs
from gutcheck.packs import resolve as resolve_pack
from gutcheck.policy import answer_probability, verdict
from gutcheck.store import AnswerRecord, DecisionRecord, DecisionStore, FeedbackRecord

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
    packs: list[str] = []


class FeedbackItem(BaseModel):
    model_config = {"extra": "forbid"}

    # the true answer (true/false, an option, or a score level), or just whether it was right
    answer: bool | int | str | None = None
    correct: bool | None = None

    @model_validator(mode="after")
    def _one(self) -> "FeedbackItem":
        if (self.answer is None) == (self.correct is None):
            raise ValueError("give exactly one of `answer` or `correct`")
        return self


class FeedbackRequest(BaseModel):
    model_config = {"extra": "forbid"}

    trace_id: str
    answers: dict[str, FeedbackItem] = Field(min_length=1)
    source: str | None = None
    note: str | None = None


class CalibrateRequest(BaseModel):
    model_config = {"extra": "forbid"}

    min_samples: int | None = Field(None, ge=2)


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


def _add_packs(
    packs: dict[str, Pack],
    refs: list[str],
    policy: Thresholds | None,
    default: Thresholds,
    questions: dict[str, dict[str, Any]],
    thresholds: dict[str, Thresholds],
) -> dict[str, float]:
    """Add each pack's questions as "<pack>.<question>"; return their temperatures."""
    temperatures = {}
    for ref in refs:
        try:
            pack = resolve_pack(packs, ref)
        except PackError as e:
            raise HTTPException(422, str(e)) from e
        for qid, q in pack.questions.items():
            full = f"{pack.id}.{qid}"
            if full in questions:
                raise HTTPException(422, f"question {full!r} is defined twice")
            questions[full] = q.payload()
            thresholds[full] = policy or q.policy or default
            temperatures[full] = pack.temperatures.get(qid, 1.0)
    return temperatures


def _eval_summary(pack: Pack) -> dict[str, Any] | None:
    if pack.baseline is None:
        return None
    return {
        qid: {k: q["calibrated"][k] for k in ("n", "accuracy", "ece")}
        for qid, q in pack.baseline.get("questions", {}).items()
    }


def _record(
    trace_id: str,
    endpoint: str,
    state: State,
    questions: dict[str, dict[str, Any]],
    result: dict[str, Any],
    raw_answers: dict[str, dict[str, Any]],
    temperatures: dict[str, float],
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
                calibration_key=fingerprint(questions[qid]),
                options=options(raw_answers[qid]),
                raw=distribution(raw_answers[qid]),
                temperature=temperatures.get(qid, 1.0),
            )
            for qid, a in result.get("answers", {}).items()
        ],
    )


def _percentile(ordered: list[float], q: float) -> float | None:
    if not ordered:
        return None
    return round(ordered[min(len(ordered) - 1, int(q * len(ordered)))], 1)


def create_app(
    settings: Settings | None = None,
    engine: Engine | None = None,
    store: DecisionStore | None = None,
    packs: dict[str, Pack] | None = None,
) -> FastAPI:
    settings = settings or load_settings()
    packs = packs if packs is not None else load_packs(settings.packs.dirs)
    engine = engine or LayaEngine(settings.engine)
    metrics = Metrics()
    pack_questions = {f"{p.id}.{qid}" for p in packs.values() for qid in p.questions}
    # temperatures fitted from feedback, by question fingerprint; they override pack calibration
    learned: dict[str, float] = {}
    # one forward pass at a time; inference is blocking torch and must stay off the event loop
    pool: ThreadPoolExecutor | None = None

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        nonlocal store, pool
        owns_store = store is None and bool(settings.store.path)
        if owns_store:
            store = DecisionStore(settings.store.path, settings.store.save_state)
        if store is not None:
            learned.update(store.temperatures())
        pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="gutcheck-infer")
        engine.start()
        yield
        pool.shutdown(wait=True)
        engine.close()
        if owns_store:
            store.close()
            store = None

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

    def metric_label(qid: str) -> str:
        return qid if qid in pack_questions else "inline"

    def infer(
        endpoint: str,
        state: State,
        questions: dict[str, dict[str, Any]],
        model: str | None,
        thresholds: dict[str, Thresholds] | None,
        temperatures: dict[str, float] | None = None,
    ) -> Outcome:
        start = time.perf_counter()
        result = engine.predict(state, questions, model)
        latency_ms = (time.perf_counter() - start) * 1000

        temperatures = temperatures or {}
        raw_answers = result.get("answers", {})
        if temperatures:
            result["answers"] = {
                qid: apply_temperature(a, temperatures.get(qid, 1.0))
                for qid, a in raw_answers.items()
            }
        answers = result.get("answers", {})
        probabilities = {qid: answer_probability(a) for qid, a in answers.items()}
        verdicts = (
            {qid: verdict(p, thresholds[qid]) for qid, p in probabilities.items()}
            if thresholds is not None
            else None
        )
        model_name = (result.get("routing") or {}).get("model") or "unknown"
        metrics.decisions.labels(endpoint, model_name).inc()
        metrics.inference.labels(endpoint).observe(latency_ms / 1000)
        for qid, v in (verdicts or {}).items():
            metrics.verdicts.labels(metric_label(qid), v).inc()
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
                        raw_answers,
                        temperatures,
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

    @app.get("/v1/packs", dependencies=[Depends(require_key)])
    def list_packs() -> dict[str, Any]:
        return {
            "packs": [
                {
                    "id": p.id,
                    "version": p.version,
                    "description": p.description,
                    "questions": {
                        qid: {"type": q.type, "instructions": q.instructions}
                        for qid, q in p.questions.items()
                    },
                    "calibrated": bool(p.temperatures),
                    "eval": _eval_summary(p),
                }
                for p in packs.values()
            ]
        }

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
        temperatures = _add_packs(
            packs, req.packs, req.policy, settings.policy, questions, thresholds
        )
        for qid, q in questions.items():
            t = learned.get(fingerprint(q))
            if t is not None:
                temperatures[qid] = t
        out = await run("decide", req.state, questions, req.model, thresholds, temperatures)
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

    def require_store() -> DecisionStore:
        if store is None:
            raise HTTPException(409, "the decision log is disabled (store.path is null)")
        return store

    @app.post("/v1/feedback", dependencies=[Depends(require_key)])
    def feedback(req: FeedbackRequest) -> dict[str, Any]:
        """Record the true answers for a logged decision."""
        db = require_store()
        if not db.has_decision(req.trace_id):
            raise HTTPException(404, f"no decision with trace id {req.trace_id!r}")
        records, recorded = [], []
        for qid, item in req.answers.items():
            logged = db.answer(req.trace_id, qid)
            if logged is None:
                raise HTTPException(404, f"decision {req.trace_id!r} has no question {qid!r}")
            if logged["raw"] is None:
                raise HTTPException(422, f"question {qid!r} was logged before feedback existed")
            try:
                label, correct = resolve(
                    logged["options"], logged["raw"], item.answer, item.correct
                )
            except ValueError as e:
                raise HTTPException(422, f"question {qid!r}: {e}") from e
            records.append(FeedbackRecord(req.trace_id, qid, label, correct, req.source, req.note))
            recorded.append(
                {
                    "question_id": qid,
                    "answer": logged["options"][label] if label is not None else None,
                    "correct": correct,
                }
            )
        db.add_feedback(records)
        for r in records:
            metrics.feedback.labels(metric_label(r.question_id), str(r.correct).lower()).inc()
        return {"trace_id": req.trace_id, "recorded": recorded}

    @app.post("/v1/calibrate", dependencies=[Depends(require_key)])
    def calibrate(req: CalibrateRequest | None = None) -> dict[str, Any]:
        """Refit temperatures from feedback and apply them to new decisions."""
        db = require_store()
        min_samples = (req and req.min_samples) or settings.calibration.min_samples
        refits = recalibrate(db, min_samples)
        learned.update({k: r.temperature for k, r in refits.items() if r.temperature})
        described = db.questions()
        return {
            "min_samples": min_samples,
            "questions": [
                {
                    "calibration_key": key,
                    "question_id": described.get(key, {}).get("question_id"),
                    **vars(r),
                }
                for key, r in refits.items()
            ],
        }

    @app.get("/v1/stats", dependencies=[Depends(require_key)])
    def stats(hours: int = Query(24, ge=1, le=24 * 90)) -> dict[str, Any]:
        """Traffic, verdicts and feedback accuracy for the dashboard."""
        db = require_store()
        since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        raw = db.stats(since)
        described = db.questions()
        per_q: dict[str, dict[str, Any]] = {}
        for key, v, count in raw["per_question"]:
            q = per_q.setdefault(key, {"answers": 0, "verdicts": {}})
            q["answers"] += count
            if v is not None:
                q["verdicts"][v] = count
        for key, n, n_correct in raw["labelled"]:
            q = per_q.setdefault(key, {"answers": 0, "verdicts": {}})
            q["feedback"] = n
            q["accuracy"] = round(n_correct / n, 4)
        questions = []
        for key, q in per_q.items():
            d = described.get(key, {})
            questions.append(
                {
                    "calibration_key": key,
                    "question_id": d.get("question_id"),
                    "type": d.get("type"),
                    "instructions": d.get("instructions"),
                    "answers": q["answers"],
                    "verdicts": q["verdicts"],
                    "feedback": q.get("feedback", 0),
                    "accuracy": q.get("accuracy"),
                    "temperature": learned.get(key),
                }
            )
        questions.sort(key=lambda q: -q["answers"])
        verdicts: dict[str, int] = {}
        for q in questions:
            for v, n in q["verdicts"].items():
                verdicts[v] = verdicts.get(v, 0) + n
        return {
            "hours": hours,
            "decisions": len(raw["latencies"]),
            "per_hour": [{"hour": h + ":00Z", "decisions": n} for h, n in raw["per_hour"]],
            "latency_ms": {
                "p50": _percentile(raw["latencies"], 0.5),
                "p95": _percentile(raw["latencies"], 0.95),
            },
            "verdicts": verdicts,
            "questions": questions,
        }

    @app.get("/metrics", dependencies=[Depends(require_key)])
    def prometheus() -> Response:
        return Response(generate_latest(metrics.registry), media_type=CONTENT_TYPE_LATEST)

    @app.get("/dashboard", response_class=HTMLResponse, include_in_schema=False)
    def dashboard() -> str:
        return resources.files("gutcheck").joinpath("static/dashboard.html").read_text()

    return app
