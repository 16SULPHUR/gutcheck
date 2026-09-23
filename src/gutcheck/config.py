import os
from contextvars import ContextVar
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, SecretStr, model_validator
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
    # checkpoints loaded at startup; others load on first use
    models: list[LayaModel] = ["english", "multilingual"]
    # 2 fits a 4 GB GPU in fp16
    max_loaded: int = Field(2, ge=1, le=3)


class Thresholds(BaseModel):
    """Verdict bands on the probability of the returned answer."""

    model_config = {"extra": "forbid"}

    act_at: float = Field(0.9, ge=0, le=1)
    review_at: float = Field(0.6, ge=0, le=1)

    @model_validator(mode="after")
    def _ordered(self) -> "Thresholds":
        if self.review_at > self.act_at:
            raise ValueError("review_at must not be greater than act_at")
        return self


class StoreSettings(BaseModel):
    model_config = {"extra": "forbid"}

    # SQLite file for the decision log; null disables logging
    path: str | None = "gutcheck.db"
    # store the request state (the input text) alongside each decision
    save_state: bool = True


class Settings(BaseSettings):
    """Precedence: explicit overrides > GUTCHECK_* env vars > YAML config file > defaults."""

    model_config = SettingsConfigDict(
        env_prefix="GUTCHECK_", env_nested_delimiter="__", extra="forbid"
    )

    host: str = "127.0.0.1"
    port: int = Field(8080, ge=1, le=65535)
    log_level: Literal["critical", "error", "warning", "info", "debug"] = "info"
    api_key: SecretStr | None = None
    engine: EngineSettings = EngineSettings()
    policy: Thresholds = Thresholds()
    store: StoreSettings = StoreSettings()

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
