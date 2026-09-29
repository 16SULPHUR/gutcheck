# Packs, stats, metrics

## GET /v1/packs

Lists installed packs: id, version, description, questions, the pinned `model` if any, whether it ships `calibrated`, and headline `eval` numbers.

## GET /v1/stats

Traffic and feedback accuracy, used by the dashboard.

| Query | Default | Notes |
| --- | --- | --- |
| `hours` | 24 | 1 to 2160 |

Returns `decisions`, `per_hour`, `latency_ms` (`p50`, `p95`), the overall `verdicts` mix, and per-question `answers`, `verdicts`, `feedback`, `accuracy` and learned `temperature`.

## GET /metrics

Prometheus metrics:

| Metric | Meaning |
| --- | --- |
| `gutcheck_decisions_total` | Decisions served, by endpoint and model |
| `gutcheck_inference_seconds` | Inference latency histogram, by endpoint |
| `gutcheck_verdicts_total` | Verdicts, by question and verdict |
| `gutcheck_feedback_total` | Feedback labels, by question and whether correct |

Pack questions are labelled by name. Inline questions share the label `inline`.

## GET /dashboard

A built-in page with traffic, latency, the verdict mix and per-question accuracy over the last day, week or month. It reads `/v1/stats`.

![gutcheck dashboard](/dashboard.png)

## GET /healthz

Returns `status`, `version` and which Laya checkpoints are loaded. Never requires the API key.
