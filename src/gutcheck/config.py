import os
from contextvars import ContextVar
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    YamlConfigSettingsSource,
)

LayaModel = Literal["english", "multilingual", "typed-decisions"]

_config_file: ContextVar[Path | None] = ContextVar("gutcheck_config_file", default=None)


class EngineSettings(BaseModel):
    model_config = {"extra": "forbid"}

    device: str | None = None
    models: list[LayaModel] = ["english", "multilingual"]
    # 2 fits a 4 GB GPU in fp16
    max_loaded: int = Field(2, ge=1, le=3)


class Settings(BaseSettings):
    """Precedence: explicit overrides > GUTCHECK_* env vars > YAML config file > defaults."""

    model_config = SettingsConfigDict(
        env_prefix="GUTCHECK_", env_nested_delimiter="__", extra="forbid"
    )

    host: str = "127.0.0.1"
    port: int = Field(8080, ge=1, le=65535)
    log_level: Literal["critical", "error", "warning", "info", "debug"] = "info"
    engine: EngineSettings = EngineSettings()

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        yaml_settings = YamlConfigSettingsSource(settings_cls, yaml_file=_config_file.get())
        return init_settings, env_settings, yaml_settings


def load_settings(config: str | Path | None = None, **overrides) -> Settings:
    """Load settings, reading the YAML file from `config` or $GUTCHECK_CONFIG if given."""
    path = config or os.environ.get("GUTCHECK_CONFIG")
    if path:
        path = Path(path)
        if not path.is_file():
            raise FileNotFoundError(f"config file not found: {path}")
    token = _config_file.set(path or None)
    try:
        return Settings(**overrides)
    finally:
        _config_file.reset(token)
