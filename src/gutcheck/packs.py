import json
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, PrivateAttr, field_validator

from gutcheck.config import Thresholds

BUNDLED_DIR = Path(__file__).parent / "packs"


class PackError(ValueError):
    pass


def label_key(value: Any) -> str:
    """Dataset labels and YAML keys as strings; booleans become "true"/"false"."""
    return str(value).lower() if isinstance(value, bool) else str(value)


class DatasetSpec(BaseModel):
    model_config = {"extra": "forbid"}

    # Hugging Face repo; without one, `path` is relative to the pack directory
    repo: str | None = None
    # held-out splits can ship inside a model repo next to the checkpoint they calibrate
    repo_type: Literal["dataset", "model"] = "dataset"
    revision: str = "main"
    path: str
    license: str


class EvalSpec(BaseModel):
    model_config = {"extra": "forbid"}

    test: DatasetSpec
    calibration: DatasetSpec | None = None
    text_field: str
    label_field: str
    # dataset label -> answer: true/false for noul, an option for choice, a level index for score.
    # Quote keys like "yes"/"no": YAML reads them as booleans.
    labels: dict[str, bool | str | int]
    max_rows: int | None = Field(None, ge=1)
    calibration_max_rows: int | None = Field(300, ge=1)

    @field_validator("labels", mode="before")
    @classmethod
    def _str_keys(cls, v: Any) -> Any:
        return {label_key(k): val for k, val in v.items()} if isinstance(v, dict) else v


class PackQuestion(BaseModel):
    model_config = {"extra": "forbid"}

    type: Literal["choice", "score", "noul"]
    instructions: str
    criteria: dict[str, Any] | list[Any] | None = None
    labels: dict[str, str] | None = None
    policy: Thresholds | None = None
    eval: EvalSpec

    @field_validator("criteria", mode="before")
    @classmethod
    def _str_criteria_keys(cls, v: Any) -> Any:
        # YAML reads unquoted true/false keys as booleans
        return {label_key(k): val for k, val in v.items()} if isinstance(v, dict) else v

    def payload(self) -> dict[str, Any]:
        """The question as sent to Laya."""
        return self.model_dump(
            include={"type", "instructions", "criteria", "labels"}, exclude_none=True
        )

    def label_index(self, value: bool | str | int) -> int:
        """Index of a mapped answer in this question's option order."""
        if self.type == "noul":
            if isinstance(value, str):
                value = value.strip().lower() == "true"
            return int(bool(value))
        if self.type == "score":
            return int(value)
        options = list(self.criteria) if isinstance(self.criteria, (dict, list)) else []
        if value not in options:
            raise PackError(f"label {value!r} is not an option of this question")
        return options.index(value)


class ModelSpec(BaseModel):
    """A Laya checkpoint fine-tuned for this pack's questions."""

    model_config = {"extra": "forbid"}

    # Hugging Face model repo, or a directory relative to the pack
    repo: str
    revision: str = "main"
    subfolder: str | None = None


class Pack(BaseModel):
    model_config = {"extra": "forbid"}

    id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]*$")
    version: int = Field(ge=1)
    description: str
    # questions run on this checkpoint instead of the routed base models
    model: ModelSpec | None = None
    questions: dict[str, PackQuestion] = Field(min_length=1)

    _directory: Path = PrivateAttr(default=Path("."))
    _temperatures: dict[str, float] = PrivateAttr(default_factory=dict)
    _baseline: dict[str, Any] | None = PrivateAttr(default=None)

    @property
    def directory(self) -> Path:
        return self._directory

    @property
    def checkpoint(self) -> str | None:
        """Engine name of the pack's own checkpoint, if it has one."""
        return f"{self.id}@{self.version}" if self.model else None

    def model_source(self) -> str:
        """Local directory or Hugging Face repo id of the pack's checkpoint."""
        assert self.model is not None
        local = self._directory / self.model.repo
        return str(local) if local.is_dir() else self.model.repo

    @property
    def temperatures(self) -> dict[str, float]:
        return self._temperatures

    @property
    def baseline(self) -> dict[str, Any] | None:
        return self._baseline

    @classmethod
    def load(cls, directory: Path) -> "Pack":
        try:
            data = yaml.safe_load((directory / "pack.yaml").read_text())
            pack = cls.model_validate(data)
        except Exception as e:
            raise PackError(f"invalid pack in {directory}: {e}") from e
        pack._directory = directory
        cal = directory / "calibration.json"
        if cal.exists():
            temps = json.loads(cal.read_text()).get("temperatures", {})
            pack._temperatures = {q: float(t) for q, t in temps.items() if q in pack.questions}
        baseline = directory / "eval.json"
        if baseline.exists():
            pack._baseline = json.loads(baseline.read_text())
        return pack


def load_packs(extra_dirs: list[str] | None = None) -> dict[str, Pack]:
    """Bundled packs, then packs from `extra_dirs`; a later pack replaces one with the same id."""
    packs: dict[str, Pack] = {}
    for root in [BUNDLED_DIR, *(Path(d) for d in extra_dirs or [])]:
        for pack_yaml in sorted(root.glob("*/pack.yaml")):
            pack = Pack.load(pack_yaml.parent)
            packs[pack.id] = pack
    return packs


def resolve(packs: dict[str, Pack], ref: str) -> Pack:
    """Look up "id" or "id@version"."""
    pack_id, _, version = ref.partition("@")
    pack = packs.get(pack_id)
    if pack is None:
        raise PackError(f"unknown pack {pack_id!r}; installed: {sorted(packs)}")
    if version and version != str(pack.version):
        raise PackError(f"pack {pack_id!r} is version {pack.version}, not {version}")
    return pack
