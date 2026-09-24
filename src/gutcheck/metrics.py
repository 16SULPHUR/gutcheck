from prometheus_client import CollectorRegistry, Counter, Histogram


class Metrics:
    """Prometheus metrics for one app instance (own registry, so tests can build many apps)."""

    def __init__(self) -> None:
        self.registry = CollectorRegistry()
        self.decisions = Counter(
            "gutcheck_decisions",
            "Decisions served",
            ["endpoint", "model"],
            registry=self.registry,
        )
        self.inference = Histogram(
            "gutcheck_inference_seconds",
            "Model inference time per request",
            ["endpoint"],
            buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
            registry=self.registry,
        )
        # pack questions are labelled by name; inline questions share "inline" to bound cardinality
        self.verdicts = Counter(
            "gutcheck_verdicts",
            "Verdicts per question",
            ["question", "verdict"],
            registry=self.registry,
        )
        self.feedback = Counter(
            "gutcheck_feedback",
            "Labelled answers received",
            ["question", "correct"],
            registry=self.registry,
        )
