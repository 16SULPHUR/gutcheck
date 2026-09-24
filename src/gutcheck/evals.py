import csv
import json
import random
import statistics
import time
import urllib.request
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path
from typing import Any

from gutcheck import __version__
from gutcheck.calibration import distribution, ece, fit_temperature, scale
from gutcheck.config import Thresholds
from gutcheck.engine import Engine
from gutcheck.packs import DatasetSpec, Pack, PackQuestion, label_key
from gutcheck.policy import verdict

DEFAULT_CACHE = Path.home() / ".cache" / "gutcheck" / "datasets"
# a fresh run may be this much worse than the committed baseline before --check fails
ACCURACY_TOLERANCE = 0.02
ECE_TOLERANCE = 0.03


@dataclass
class Row:
    state: str
    label: int


@dataclass
class Prediction:
    probs: list[float]
    label: int
    latency_ms: float
    model: str | None


def fetch(
    spec: DatasetSpec, pack_dir: Path, cache_dir: Path = DEFAULT_CACHE
) -> tuple[Path, str | None]:
    """Local path of a dataset file (downloaded and cached if needed) and its commit, if known."""
    if spec.repo is None:
        return pack_dir / spec.path, None
    target = cache_dir / spec.repo / spec.revision / spec.path
    commit_file = target.parent / (target.name + ".commit")
    if not target.exists():
        kind = "datasets/" if spec.repo_type == "dataset" else ""
        url = f"https://huggingface.co/{kind}{spec.repo}/resolve/{spec.revision}/{spec.path}"
        with urllib.request.urlopen(url, timeout=120) as resp:
            data = resp.read()
            commit = resp.headers.get("X-Repo-Commit") or ""
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        commit_file.write_text(commit)
    commit = commit_file.read_text().strip() if commit_file.exists() else ""
    # LFS files redirect to a CDN that drops X-Repo-Commit; a pinned SHA is the commit anyway
    if not commit and len(spec.revision) == 40:
        commit = spec.revision
    return target, commit or None


def read_records(path: Path) -> list[dict[str, Any]]:
    if path.suffix == ".csv":
        with path.open(newline="", encoding="utf-8") as f:
            return list(csv.DictReader(f))
    if path.suffix == ".jsonl":
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    if path.suffix == ".parquet":
        try:
            import pyarrow.parquet as pq
        except ImportError as e:
            raise RuntimeError("parquet datasets need pyarrow: pip install 'gutcheck[eval]'") from e
        return pq.read_table(path).to_pylist()
    raise ValueError(f"unsupported dataset format: {path.name}")


def load_rows(
    question: PackQuestion,
    spec: DatasetSpec,
    pack_dir: Path,
    max_rows: int | None,
    cache_dir: Path = DEFAULT_CACHE,
) -> tuple[list[Row], str | None]:
    path, commit = fetch(spec, pack_dir, cache_dir)
    ev = question.eval
    rows = []
    for rec in read_records(path):
        raw = label_key(rec[ev.label_field])
        if raw not in ev.labels:
            raise ValueError(f"{spec.path}: label {raw!r} has no mapping in the pack")
        rows.append(Row(str(rec[ev.text_field]), question.label_index(ev.labels[raw])))
    if max_rows is not None and len(rows) > max_rows:
        keep = sorted(random.Random(0).sample(range(len(rows)), max_rows))
        rows = [rows[i] for i in keep]
    return rows, commit


def predict(
    engine: Engine, question: PackQuestion, rows: list[Row], model: str | None = None
) -> list[Prediction]:
    payload = {"q": question.payload()}
    preds = []
    for row in rows:
        start = time.perf_counter()
        result = engine.predict(row.state, payload, model)
        latency_ms = (time.perf_counter() - start) * 1000
        model = (result.get("routing") or {}).get("model")
        preds.append(Prediction(distribution(result["answers"]["q"]), row.label, latency_ms, model))
    return preds


def _pct(values: list[float], q: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(q * len(ordered)))]


def metrics(
    question: PackQuestion,
    preds: list[Prediction],
    thresholds: Thresholds,
    temperature: float = 1.0,
) -> dict[str, Any]:
    probs = [scale(p.probs, temperature) for p in preds]
    labels = [p.label for p in preds]
    top = [max(range(len(q)), key=q.__getitem__) for q in probs]
    conf = [max(q) for q in probs]
    correct = [t == y for t, y in zip(top, labels, strict=True)]
    verdicts = Counter(verdict(c, thresholds) for c in conf)
    acted = [ok for ok, c in zip(correct, conf, strict=True) if verdict(c, thresholds) == "act"]
    n = len(preds)
    brier = statistics.fmean(
        sum((qi - (i == y)) ** 2 for i, qi in enumerate(q))
        for q, y in zip(probs, labels, strict=True)
    )
    out: dict[str, Any] = {
        "n": n,
        "accuracy": statistics.fmean(correct),
        # binary questions report the usual (p - y)^2; the sum over both classes is twice that
        "brier": brier / 2 if question.type == "noul" else brier,
        "ece": ece(conf, correct),
        "act_rate": verdicts["act"] / n,
        "act_accuracy": statistics.fmean(acted) if acted else None,
        "review_rate": verdicts["review"] / n,
        "escalate_rate": verdicts["escalate"] / n,
    }
    if question.type == "noul":
        tp = sum(1 for t, y in zip(top, labels, strict=True) if t == 1 and y == 1)
        pred_pos, real_pos = top.count(1), labels.count(1)
        precision = tp / pred_pos if pred_pos else 0.0
        recall = tp / real_pos if real_pos else 0.0
        out["precision"] = precision
        out["recall"] = recall
        out["f1"] = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return out


def evaluate_pack(
    engine: Engine,
    pack: Pack,
    default_policy: Thresholds,
    calibrate: bool = False,
    cache_dir: Path = DEFAULT_CACHE,
    log=print,
) -> dict[str, Any]:
    """Evaluate every question of a pack; optionally refit temperatures first."""
    report: dict[str, Any] = {
        "pack": pack.id,
        "version": pack.version,
        "gutcheck": __version__,
        "laya": _version("laya"),
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "questions": {},
    }
    temperatures = dict(pack.temperatures)
    model = pack.checkpoint
    if model:
        engine.add_checkpoint(model, pack.model_source(), pack.model.revision, pack.model.subfolder)
    for qid, question in pack.questions.items():
        ev = question.eval
        thresholds = question.policy or default_policy
        if calibrate and ev.calibration is not None:
            rows, _ = load_rows(
                question, ev.calibration, pack.directory, ev.calibration_max_rows, cache_dir
            )
            log(f"{pack.id}.{qid}: fitting temperature on {len(rows)} rows")
            cal = predict(engine, question, rows, model)
            temperatures[qid] = fit_temperature([(p.probs, p.label) for p in cal])
        rows, commit = load_rows(question, ev.test, pack.directory, ev.max_rows, cache_dir)
        log(f"{pack.id}.{qid}: evaluating {len(rows)} rows")
        preds = predict(engine, question, rows, model)
        temperature = temperatures.get(qid, 1.0)
        latencies = [p.latency_ms for p in preds]
        report["questions"][qid] = {
            "dataset": {**ev.test.model_dump(), "commit": commit},
            "temperature": round(temperature, 4),
            "thresholds": thresholds.model_dump(),
            "raw": _rounded(metrics(question, preds, thresholds)),
            "calibrated": _rounded(metrics(question, preds, thresholds, temperature)),
            "latency_ms": {
                "p50": round(_pct(latencies, 0.5), 1),
                "p95": round(_pct(latencies, 0.95), 1),
            },
            "models": dict(Counter(p.model for p in preds)),
        }
    report["temperatures"] = {q: round(t, 4) for q, t in temperatures.items()}
    return report


def _version(dist: str) -> str:
    try:
        return metadata.version(dist)
    except metadata.PackageNotFoundError:
        return "unknown"


def _rounded(m: dict[str, Any]) -> dict[str, Any]:
    return {k: round(v, 4) if isinstance(v, float) else v for k, v in m.items()}


def check(report: dict[str, Any], baseline: dict[str, Any] | None) -> list[str]:
    """Regressions of `report` against `baseline`; empty when it holds up."""
    if baseline is None:
        return ["no committed baseline (eval.json)"]
    problems = []
    for qid, cur in report["questions"].items():
        base = baseline.get("questions", {}).get(qid)
        if base is None:
            problems.append(f"{qid}: not in the baseline")
            continue
        now, then = cur["calibrated"], base["calibrated"]
        if now["accuracy"] < then["accuracy"] - ACCURACY_TOLERANCE:
            problems.append(
                f"{qid}: accuracy {now['accuracy']:.3f} < baseline {then['accuracy']:.3f}"
            )
        if now["ece"] > then["ece"] + ECE_TOLERANCE:
            problems.append(f"{qid}: ECE {now['ece']:.3f} > baseline {then['ece']:.3f}")
    return problems


def _fmt(v: Any) -> str:
    if v is None:
        return "–"
    return f"{v:.3f}" if isinstance(v, float) else str(v)


def render_markdown(report: dict[str, Any], pack: Pack) -> str:
    lines = [
        f"# {pack.id} v{pack.version}: evaluation",
        "",
        f"Generated by `gutcheck eval {pack.id}` on {report['generated_at']} "
        f"(gutcheck {report['gutcheck']}, laya {report['laya']}). Do not edit by hand.",
        "",
        "Calibrated rows use a temperature fitted on each dataset's separate training split,",
        "so the test rows below were never seen during fitting. Laya's base checkpoints are",
        "not trained on these tasks; the numbers show what you get out of the box.",
        "",
    ]
    for qid, q in report["questions"].items():
        ds = q["dataset"]
        source = (
            f"[{ds['repo']}](https://huggingface.co/datasets/{ds['repo']})"
            if ds["repo"]
            else ds["path"]
        )
        commit = f" @ `{ds['commit'][:10]}`" if ds.get("commit") else ""
        th = q["thresholds"]
        lines += [
            f"## `{pack.id}.{qid}`",
            "",
            f"Test set: {source}{commit}, `{ds['path']}`, {q['raw']['n']} rows, "
            f"license {ds['license']}. "
            f"Checkpoints used: {', '.join(f'{m} ({c})' for m, c in q['models'].items())}. "
            f"Fitted temperature: {q['temperature']}. Verdict thresholds: act ≥ {th['act_at']}, "
            f"review ≥ {th['review_at']}.",
            "",
            "| Metric | Raw | Calibrated |",
            "| --- | --- | --- |",
        ]
        for key, label in [
            ("accuracy", "Accuracy"),
            ("precision", "Precision"),
            ("recall", "Recall"),
            ("f1", "F1"),
            ("brier", "Brier score (lower is better)"),
            ("ece", "ECE (lower is better)"),
            ("act_rate", "Share of answers marked act"),
            ("act_accuracy", "Accuracy of act answers"),
            ("review_rate", "Share marked review"),
            ("escalate_rate", "Share marked escalate"),
        ]:
            if key in q["raw"]:
                lines.append(f"| {label} | {_fmt(q['raw'][key])} | {_fmt(q['calibrated'][key])} |")
        lat = q["latency_ms"]
        lines += ["", f"Latency per request: p50 {lat['p50']} ms, p95 {lat['p95']} ms.", ""]
    return "\n".join(lines)


def write_outputs(report: dict[str, Any], pack: Pack, calibrated: bool) -> None:
    d = pack.directory
    (d / "eval.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    (d / "EVAL.md").write_text(render_markdown(report, pack))
    if calibrated:
        cal = {"temperatures": report["temperatures"]}
        (d / "calibration.json").write_text(json.dumps(cal, indent=2) + "\n")


def render_summary(
    report: dict[str, Any], pack: Pack, problems: list[str], calibrated: bool
) -> str:
    """Markdown for a CI comment: the check result, the report, and the files to commit."""
    status = "\n".join(f"- ❌ {p}" for p in problems) or "- ✅ within tolerance of the baseline"
    files = [("eval.json", json.dumps(report, indent=2, ensure_ascii=False))]
    if calibrated:
        files.append(("calibration.json", json.dumps({"temperatures": report["temperatures"]})))
    blocks = [
        f"<details><summary><code>{pack.id}/{name}</code></summary>\n\n```json\n{body}\n```\n\n"
        "</details>"
        for name, body in files
    ]
    body = render_markdown(report, pack).split("\n", 1)[1]
    return "\n".join([f"## {pack.id} v{pack.version}", "", status, body, *blocks, ""])
