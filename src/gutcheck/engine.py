from typing import Any, Protocol

from gutcheck.config import EngineSettings

# Hugging Face ids a client may send as `model`; the root bundle id means "let the router choose"
_PUBLISHED_IDS = {
    "convaiinnovations/laya-multilingual": "multilingual",
    "convaiinnovations/laya-typed-decisions": "typed-decisions",
}


class Engine(Protocol):
    backend: str

    def start(self) -> None: ...

    def predict(
        self, state: Any, questions: dict[str, Any], model: str | None = None
    ) -> dict[str, Any]: ...

    def loaded(self) -> list[str]: ...

    def close(self) -> None: ...


def resolve_model(model: str | None) -> str | None:
    """Map a request's `model` to a Laya checkpoint, or None to auto-route.

    Unknown ids (e.g. a Jev client's "jev-latest") auto-route instead of failing.
    """
    if not model:
        return None
    from laya.router import normalise_name

    key = str(model).strip().lower()
    if key in _PUBLISHED_IDS:
        return _PUBLISHED_IDS[key]
    try:
        return normalise_name(key)
    except ValueError:
        return None


class LayaEngine:
    backend = "laya"

    def __init__(self, cfg: EngineSettings, router: Any = None):
        if router is None:
            from laya import Router

            router = Router(device=cfg.device, max_loaded=cfg.max_loaded)
        self._cfg = cfg
        self._router = router

    def start(self) -> None:
        if self._cfg.models:
            self._router.preload(list(self._cfg.models))

    def predict(
        self, state: Any, questions: dict[str, Any], model: str | None = None
    ) -> dict[str, Any]:
        return self._router.predict(state, questions, model=resolve_model(model))

    def loaded(self) -> list[str]:
        return list(self._router.loaded)

    def close(self) -> None:
        self._router.unload()
