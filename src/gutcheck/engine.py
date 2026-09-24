import os
import threading
from collections.abc import Callable
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

    def add_checkpoint(
        self, name: str, source: str, revision: str = "main", subfolder: str | None = None
    ) -> None: ...

    def close(self) -> None: ...


# the files a Laya checkpoint needs; the rest of a repo (READMEs, held-out data) is skipped
_CHECKPOINT_FILES = ("rl_agent_config.json", "model.safetensors", "tokenizer/*", "encoder/*")


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

    def __init__(
        self,
        cfg: EngineSettings,
        router: Any = None,
        agent_factory: Callable[[str, str | None], Any] | None = None,
    ):
        if router is None:
            from laya import Router

            router = Router(device=cfg.device, max_loaded=cfg.max_loaded)
        self._cfg = cfg
        self._router = router
        self._agent_factory = agent_factory or self._build_agent
        # pack checkpoints live outside the router, which only knows Laya's published models
        self._checkpoints: dict[str, tuple[str, str, str | None]] = {}
        self._agents: dict[str, Any] = {}
        self._lock = threading.Lock()

    def _build_agent(self, path: str, subfolder: str | None) -> Any:
        from laya import Agent

        return Agent(path, device=self._cfg.device, subfolder=subfolder)

    def add_checkpoint(
        self, name: str, source: str, revision: str = "main", subfolder: str | None = None
    ) -> None:
        self._checkpoints[name] = (source, revision, subfolder)

    def _checkpoint_agent(self, name: str) -> Any:
        with self._lock:
            if name not in self._agents:
                source, revision, subfolder = self._checkpoints[name]
                if not os.path.isdir(source):
                    from huggingface_hub import snapshot_download

                    prefix = f"{subfolder}/" if subfolder else ""
                    source = snapshot_download(
                        source,
                        revision=revision,
                        allow_patterns=[prefix + f for f in _CHECKPOINT_FILES],
                    )
                self._agents[name] = self._agent_factory(source, subfolder)
            return self._agents[name]

    def start(self) -> None:
        if self._cfg.models:
            self._router.preload(list(self._cfg.models))

    def predict(
        self, state: Any, questions: dict[str, Any], model: str | None = None
    ) -> dict[str, Any]:
        if model in self._checkpoints:
            result = self._checkpoint_agent(model).system_one(state, questions)
            return {**result, "routing": {"model": model, "reason": "pack checkpoint"}}
        return self._router.predict(state, questions, model=resolve_model(model))

    def loaded(self) -> list[str]:
        return list(self._router.loaded) + list(self._agents)

    def close(self) -> None:
        self._router.unload()
        with self._lock:
            self._agents.clear()
