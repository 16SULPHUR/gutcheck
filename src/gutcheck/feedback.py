import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from gutcheck.calibration import ece, fit_temperature, scale
from gutcheck.packs import label_key
from gutcheck.store import DecisionStore


def fingerprint(question: dict[str, Any]) -> str:
    """Stable key for a question definition: same wording and options, same key."""
    core = {k: question.get(k) for k in ("type", "instructions", "criteria", "labels")}
    digest = hashlib.sha256(json.dumps(core, sort_keys=True, ensure_ascii=False).encode())
    return digest.hexdigest()[:16]


def options(answer: dict[str, Any]) -> list[str]:
    """Option names in the order of `calibration.distribution(answer)`."""
    if answer["type"] == "noul":
        return ["false", "true"]
    return [str(k) for k in answer["probabilities"]]


def _top(raw: list[float]) -> int:
    return max(range(len(raw)), key=raw.__getitem__)


def resolve(
    opts: list[str], raw: list[float], answer: Any = None, correct: bool | None = None
) -> tuple[int | None, bool]:
    """(index of the true option or None if unknown, whether the returned answer was right)."""
    returned = _top(raw)
    if answer is not None:
        key = label_key(answer)
        if key not in opts:
            raise ValueError(f"{answer!r} is not one of the options {opts}")
        label = opts.index(key)
        return label, label == returned
    if correct is None:
        raise ValueError("give either `answer` or `correct`")
    if correct:
        return returned, True
    # a wrong yes/no answer implies the other option; with more options the truth is unknown
    return (1 - returned if len(opts) == 2 else None), False


@dataclass
class Refit:
    n: int
    temperature: float | None = None
    accuracy: float | None = None
    ece_before: float | None = None
    ece_after: float | None = None


def recalibrate(store: DecisionStore, min_samples: int) -> dict[str, Refit]:
    """Fit a temperature per question from labelled answers and save it to the store.

    Questions with fewer than `min_samples` labels are reported but left unchanged.
    """
    samples: dict[str, list[tuple[list[float], int]]] = defaultdict(list)
    for key, raw, label in store.labelled():
        samples[key].append((raw, label))
    out: dict[str, Refit] = {}
    fitted: dict[str, tuple[float, int]] = {}
    for key, rows in samples.items():
        if len(rows) < min_samples:
            out[key] = Refit(n=len(rows))
            continue
        t = fit_temperature(rows)
        correct = [_top(raw) == label for raw, label in rows]
        before = [max(raw) for raw, _ in rows]
        after = [max(scale(raw, t)) for raw, _ in rows]
        out[key] = Refit(
            n=len(rows),
            temperature=round(t, 4),
            accuracy=round(sum(correct) / len(rows), 4),
            ece_before=round(ece(before, correct), 4),
            ece_after=round(ece(after, correct), 4),
        )
        fitted[key] = (round(t, 4), len(rows))
    if fitted:
        store.save_temperatures(fitted)
    return out
