from fastapi import FastAPI
from pydantic import BaseModel

from gutcheck import __version__
from gutcheck.config import LayaModel, Settings, load_settings


class EngineStatus(BaseModel):
    backend: str
    loaded: bool
    models: list[LayaModel]


class Health(BaseModel):
    status: str
    version: str
    engine: EngineStatus


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()
    app = FastAPI(title="gutcheck", version=__version__)
    app.state.settings = settings

    @app.get("/healthz", response_model=Health)
    def healthz() -> Health:
        # The Laya engine is wired in during M1; until then nothing is loaded.
        engine = EngineStatus(backend="laya", loaded=False, models=settings.engine.models)
        return Health(status="ok", version=__version__, engine=engine)

    return app
