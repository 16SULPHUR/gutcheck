# POST /v1/decide

Ask typed questions about a state and get calibrated answers, each with a verdict.

## Request

```json
{
  "state": {"subject": "Duplicate charge on invoice #4411", "body": "We were billed twice."},
  "policy": {"act_at": 0.85, "review_at": 0.6},
  "questions": {
    "department": {"type": "choice", "instructions": "Which department should handle this?",
                   "criteria": {"billing": "invoices, refunds", "technical": "bugs, outages"}},
    "refund": {"type": "noul", "instructions": "Does the customer ask for money back?",
               "policy": {"act_at": 0.95, "review_at": 0.7}}
  },
  "packs": ["prompt-guard@2"]
}
```

| Field | Type | Notes |
| --- | --- | --- |
| `state` | string, object or list of chat turns | What is being judged |
| `questions` | object | Name to question. May be empty if you use `packs` |
| `policy` | `{act_at, review_at}` | Overrides the config for this request |
| `packs` | string list | `id` or `id@version` |
| `model` | string | Force a Laya checkpoint, for example `english` |

Unknown fields are rejected.

## Response

```json
{
  "trace_id": "gc_4f9c...",
  "model": "english",
  "answers": {
    "department": {"type": "choice", "choice": "billing",
                   "probabilities": {"billing": 0.91, "technical": 0.09},
                   "confidence": 0.56, "answer_probability": 0.91, "verdict": "act"},
    "refund": {"type": "noul", "noul": 0.82, "confidence": 0.82,
               "answer_probability": 0.82, "verdict": "review"}
  },
  "routing": {"model": "english", "reason": "English Latin text"},
  "usage": {"input_tokens": 118, "output_tokens": 0},
  "latency_ms": 41.3
}
```

The numbers are illustrative. `answer_probability` is the probability of the returned answer, after calibration, and is what the [verdict](/docs/concepts/verdicts) is computed from. Pack answers are keyed `<pack>.<question>`.

The `X-Gutcheck-Trace-Id` header carries the same `trace_id`. Use it with [`/v1/feedback`](/docs/reference/feedback).

## Authentication

If `api_key` is set, send `Authorization: Bearer <key>`. `/healthz` and the dashboard page are open.
