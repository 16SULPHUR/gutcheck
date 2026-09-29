"""Fine-tune a Laya checkpoint on a pack's questions (needs torch; runs on a GPU or, slowly, CPU).

The training loop follows Laya's official Kaggle notebook: RLCD proper-scoring-rule rewards with
soft cross-entropy guidance. Each question trains on its pack's calibration split; a seeded slice
of that split is held out for temperatures, model selection and the new pack's calibration, and
the pack's test split is never touched.
"""

import json
import math
import random
import shutil
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import yaml

from gutcheck import __version__
from gutcheck.calibration import ece, fit_temperature
from gutcheck.evals import DEFAULT_CACHE, Row, load_rows
from gutcheck.packs import Pack, PackQuestion

BUNDLE_REPO = "convaiinnovations/laya"
BASES = {"english": None, "multilingual": "multilingual"}
_FILES = ("rl_agent_config.json", "model.safetensors", "tokenizer/*", "encoder/*")
SEED = 20260924


@dataclass
class TrainSettings:
    base: str = "english"
    epochs: int = 4
    micro_batch: int = 8
    grad_accum: int = 4
    lr_encoder: float = 2.5e-5
    lr_head: float = 1.0e-4
    group_size: int = 4
    sigma_start: float = 0.4
    sigma_end: float = 0.1
    heldout_fraction: float = 0.2
    # caps per question, for smoke tests
    max_train: int | None = None
    max_heldout: int | None = None


def split(rows: list[Row], fraction: float, seed: int = SEED) -> tuple[list[Row], list[Row]]:
    """(train, held out), shuffled with a fixed seed so reruns hold out the same rows."""
    order = list(range(len(rows)))
    random.Random(seed).shuffle(order)
    n = max(1, round(len(rows) * fraction))
    held = sorted(order[:n])
    train = sorted(order[n:])
    return [rows[i] for i in train], [rows[i] for i in held]


def _download_base(base: str) -> Path:
    from huggingface_hub import snapshot_download
    from laya.agent import _fix_tokenizer_config

    sub = BASES[base]
    prefix = f"{sub}/" if sub else ""
    root = Path(snapshot_download(BUNDLE_REPO, allow_patterns=[prefix + f for f in _FILES]))
    model_dir = root / sub if sub else root
    _fix_tokenizer_config(str(model_dir))
    return model_dir


class Trainer:
    def __init__(self, model_dir: Path, device: str | None = None):
        import torch
        from laya.common import build_model
        from safetensors.torch import load_file
        from transformers import AutoTokenizer

        self.torch = torch
        self.device = torch.device(device or ("cuda" if torch.cuda.is_available() else "cpu"))
        self.model_dir = model_dir
        self.cfg = json.loads((model_dir / "rl_agent_config.json").read_text())
        self.tok = AutoTokenizer.from_pretrained(str(model_dir / "tokenizer"))
        self.model = build_model(self.cfg, encoder_dir=str(model_dir / "encoder"))
        self.model.load_state_dict(load_file(str(model_dir / "model.safetensors")), strict=True)
        self.model.to(self.device)

    def items(self, question: dict[str, Any], rows: list[Row]) -> list[dict[str, Any]]:
        from laya.agent import Agent
        from laya.common import QTYPES, build_sequence, render_options

        q = Agent._to_internal(question)
        k = len(render_options(q))
        out = []
        for row in rows:
            ids, markers = build_sequence(
                self.tok, row.state, q, self.cfg["max_len"], self.cfg["head_max_len"]
            )
            if len(markers) != k:
                continue
            target = [0.0] * k
            target[row.label] = 1.0
            out.append({"ids": ids, "markers": markers, "qtype": QTYPES[q["t"]], "target": target})
        return out

    def _forward(self, batch):
        torch = self.torch
        with torch.autocast(
            device_type=self.device.type, dtype=torch.float16, enabled=self.device.type == "cuda"
        ):
            logits, act = self.model(
                batch["input_ids"].to(self.device),
                batch["attention_mask"].to(self.device),
                batch["marker_pos"].to(self.device),
                batch["marker_mask"].to(self.device),
                batch["qtype"].to(self.device),
            )
        return logits.float(), act

    def predict(self, items: list[dict[str, Any]], batch_size: int = 16) -> list[list[float]]:
        """Raw (temperature 1) probabilities per item."""
        from laya.common import collate_items

        torch = self.torch
        self.model.eval()
        out = []
        with torch.no_grad():
            for i in range(0, len(items), batch_size):
                chunk = items[i : i + batch_size]
                batch = collate_items([chunk], self.tok.pad_token_id)
                logits, _ = self._forward(batch)
                probs = torch.softmax(logits, -1).cpu().tolist()
                for row, it in zip(probs, chunk, strict=True):
                    out.append(row[: len(it["markers"])])
        return out

    def train(self, items: list[dict[str, Any]], s: TrainSettings, log=print) -> None:
        from laya.common import collate_items, proper_reward

        torch = self.torch
        model = self.model
        model.encoder.gradient_checkpointing_enable(
            gradient_checkpointing_kwargs={"use_reentrant": False}
        )
        model.head_checkpointing = True
        model.train()
        enc = [p for n, p in model.named_parameters() if n.startswith("encoder.")]
        head = [p for n, p in model.named_parameters() if not n.startswith("encoder.")]
        opt = torch.optim.AdamW(
            [{"params": enc, "lr": s.lr_encoder}, {"params": head, "lr": s.lr_head}],
            weight_decay=0.01,
        )
        steps = max(1, math.ceil(len(items) / (s.micro_batch * s.grad_accum)) * s.epochs)
        sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=steps, eta_min=1e-6)
        scaler = torch.amp.GradScaler(self.device.type, enabled=self.device.type == "cuda")
        rng = random.Random(SEED)
        start = time.time()
        for epoch in range(s.epochs):
            order = items[:]
            rng.shuffle(order)
            sigma = s.sigma_start + (s.sigma_end - s.sigma_start) * epoch / max(1, s.epochs - 1)
            total, n = 0.0, 0
            for step, i in enumerate(range(0, len(order), s.micro_batch), start=1):
                batch = collate_items([order[i : i + s.micro_batch]], self.tok.pad_token_id)
                logits, act = self._forward(batch)
                mask = batch["marker_mask"].to(self.device)
                qtype = batch["qtype"].to(self.device)
                target = batch["target"].to(self.device)
                k = mask.sum(-1, keepdim=True).float()
                # GRPO-style: sample noisy distributions around the logits, reward them with a
                # proper scoring rule, and push the logits toward the better-scoring samples
                eps = torch.randn((s.group_size, *logits.shape), device=self.device) * sigma
                eps = (eps * mask - (eps * mask).sum(-1, keepdim=True) / k) * mask
                z = logits.detach().unsqueeze(0) + eps
                q = torch.softmax(z.masked_fill(~mask, -1e4), -1)
                with torch.no_grad():
                    r = proper_reward(q, target.unsqueeze(0), qtype, mask, w_sph=0.75, w_rps=1.0)
                    adv = (r - r.mean(0, keepdim=True)) / (r.std() + 1e-6)
                logp = -(((z - logits.unsqueeze(0)) ** 2) * mask).sum(-1) / (2 * sigma**2)
                loss_rl = -(adv * logp).mean()
                logq = torch.log_softmax(logits.masked_fill(~mask, -1e4), -1)
                loss_ce = -(target * logq).sum(-1).mean()
                loss = (loss_rl + loss_ce) / s.grad_accum + 0.0 * act.sum()
                scaler.scale(loss).backward()
                if step % s.grad_accum == 0 or i + s.micro_batch >= len(order):
                    scaler.unscale_(opt)
                    torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                    scaler.step(opt)
                    scaler.update()
                    sched.step()
                    opt.zero_grad(set_to_none=True)
                total += loss.item() * s.grad_accum
                n += 1
            log(
                f"epoch {epoch + 1}/{s.epochs}: loss {total / max(1, n):.4f}, "
                f"{time.time() - start:.0f}s"
            )
        model.head_checkpointing = False
        model.eval()

    def export(self, out: Path, temperature: dict[str, float], name: str) -> None:
        from laya.common import QTYPES
        from safetensors.torch import save_file

        out.mkdir(parents=True, exist_ok=True)
        state = {k: v.half().contiguous().cpu() for k, v in self.model.state_dict().items()}
        save_file(state, str(out / "model.safetensors"))
        self.model.encoder.config.save_pretrained(str(out / "encoder"))
        self.tok.save_pretrained(str(out / "tokenizer"))
        cfg = dict(self.cfg)
        temps = list(cfg.get("temperature", [1.0, 1.0, 1.0]))
        for kind, t in temperature.items():
            temps[QTYPES[kind]] = t
        cfg.update(fine_tuned=True, model_name=name, temperature=temps)
        # per-bucket temperatures from the base checkpoint would override the new fit
        cfg.pop("temperature_by_options", None)
        (out / "rl_agent_config.json").write_text(json.dumps(cfg, indent=2))


def _metrics(probs: list[list[float]], labels: list[int]) -> dict[str, float]:
    top = [max(range(len(p)), key=p.__getitem__) for p in probs]
    correct = [t == y for t, y in zip(top, labels, strict=True)]
    return {
        "n": len(labels),
        "accuracy": round(sum(correct) / len(labels), 4),
        "ece": round(ece([max(p) for p in probs], correct), 4),
    }


def finetune(
    pack: Pack,
    out: Path,
    s: TrainSettings,
    cache_dir: Path = DEFAULT_CACHE,
    device: str | None = None,
    log=print,
) -> dict[str, Any]:
    """Train, export the checkpoint with held-out data, and write a pack that uses it."""
    base_dir = _download_base(s.base)
    trainer = Trainer(base_dir, device)
    train_items, heldout = [], {}
    report: dict[str, Any] = {
        "pack": pack.id,
        "base": {"repo": BUNDLE_REPO, "subfolder": BASES[s.base]},
        "gutcheck": __version__,
        "settings": asdict(s),
        "questions": {},
    }
    for qid, question in pack.questions.items():
        spec = question.eval.train or question.eval.calibration
        if spec is None:
            raise ValueError(f"{pack.id}.{qid} has no train or calibration split to train on")
        rows, commit = load_rows(question, spec, pack.directory, None, cache_dir)
        train, held = split(rows, s.heldout_fraction)
        train, held = train[: s.max_train], held[: s.max_heldout]
        payload = question.payload()
        items = trainer.items(payload, train)
        held_items = trainer.items(payload, held)
        base_probs = trainer.predict(held_items)
        heldout[qid] = (payload, held, held_items)
        train_items += items
        report["questions"][qid] = {
            "data": {**spec.model_dump(), "commit": commit},
            "train_rows": len(items),
            "heldout_rows": len(held_items),
            "heldout_base": _metrics(base_probs, [it["target"].index(1.0) for it in held_items]),
        }
        log(f"{pack.id}.{qid}: {len(items)} training rows, {len(held_items)} held out")

    trainer.train(train_items, s, log)

    by_type: dict[str, list[tuple[list[float], int]]] = {}
    for qid, (payload, _, held_items) in heldout.items():
        probs = trainer.predict(held_items)
        labels = [it["target"].index(1.0) for it in held_items]
        report["questions"][qid]["heldout_tuned"] = _metrics(probs, labels)
        by_type.setdefault(payload["type"], []).extend(zip(probs, labels, strict=True))
        q = report["questions"][qid]
        log(
            f"{pack.id}.{qid}: held-out accuracy {q['heldout_base']['accuracy']}"
            f" -> {q['heldout_tuned']['accuracy']}"
        )
    # Laya clamps checkpoint temperatures to [0.5, 5] on load; store what will actually apply
    temperature = {
        kind: round(min(5.0, max(0.5, fit_temperature(samples))), 4)
        for kind, samples in by_type.items()
    }
    report["temperature"] = temperature

    if out.exists():
        shutil.rmtree(out)
    trainer.export(out, temperature, f"laya-{pack.id}")
    (out / "heldout").mkdir()
    for qid, (_, held, _) in heldout.items():
        records = heldout_records(pack.questions[qid], held)
        lines = [json.dumps(r, ensure_ascii=False) for r in records]
        (out / "heldout" / f"{qid}.jsonl").write_text("\n".join(lines) + "\n")
    (out / "training.json").write_text(json.dumps(report, indent=2) + "\n")
    _write_local_pack(pack, out)
    (out / "README.md").write_text(model_card(pack, report))
    return report


def _write_local_pack(pack: Pack, out: Path) -> None:
    """A copy of the pack at the next version, using this checkpoint and its held-out rows.

    The test split is unchanged, calibration moves to the held-out rows, and the rows it trained
    on are kept as the train split.
    """
    data = yaml.safe_load((pack.directory / "pack.yaml").read_text())
    data["version"] = pack.version + 1
    data["model"] = {"repo": "../.."}
    for qid, q in data["questions"].items():
        q["eval"].setdefault("train", q["eval"]["calibration"])
        q["eval"]["calibration"] = {
            "path": f"../../heldout/{qid}.jsonl",
            "license": pack.questions[qid].eval.calibration.license,
        }
        q["eval"]["calibration_max_rows"] = None
    d = out / "pack" / pack.id
    d.mkdir(parents=True)
    (d / "pack.yaml").write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True))


def heldout_records(question: PackQuestion, rows: list[Row]) -> list[dict[str, Any]]:
    """Held-out rows in the dataset's own fields and label values, so the pack's mapping applies."""
    ev = question.eval
    raw = {question.label_index(v): k for k, v in reversed(list(ev.labels.items()))}
    return [{ev.text_field: r.state, ev.label_field: raw[r.label]} for r in rows]


def model_card(pack: Pack, report: dict[str, Any]) -> str:
    rows = "\n".join(
        f"| `{pack.id}.{qid}` | {q['train_rows']} | {q['heldout_rows']} | "
        f"{q['heldout_base']['accuracy']:.3f} | {q['heldout_tuned']['accuracy']:.3f} |"
        for qid, q in report["questions"].items()
    )
    data = "\n".join(
        f"- `{qid}`: [{q['data']['repo']}](https://huggingface.co/datasets/{q['data']['repo']}) "
        f"`{q['data']['path']}` ({q['data']['license']})"
        for qid, q in report["questions"].items()
        if q["data"].get("repo")
    )
    base = report["base"]
    base_id = base["repo"] + (f"/{base['subfolder']}" if base["subfolder"] else "")
    return f"""---
license: apache-2.0
base_model: {base["repo"]}
library_name: laya
tags: [laya, gutcheck, classification]
---

# laya-{pack.id}

A [Laya](https://huggingface.co/{base["repo"]}) checkpoint (`{base_id}`) fine-tuned for the
[gutcheck](https://github.com/16SULPHUR/gutcheck) `{pack.id}` pack: {pack.description}

It was trained with gutcheck {report["gutcheck"]} using Laya's RLCD recipe on each question's
training split. A fixed 20% slice of that split was held out and never trained on; it is in
`heldout/` and is what the numbers below and the calibration temperatures come from. The pack's
test sets were not used; see the pack's `EVAL.md` for test results.

| Question | Train rows | Held-out rows | Base accuracy | Fine-tuned accuracy |
| --- | --- | --- | --- | --- |
{rows}

Training data:

{data}

The model only answers these questions reliably, worded as in the pack. Use the base Laya
checkpoints for anything else. As with any classifier guarding an LLM, treat it as one layer of
defence.
"""


def push(out: Path, repo: str, token: str | None = None) -> str:
    """Upload the checkpoint folder to the Hub; returns the commit to pin in the pack."""
    from huggingface_hub import HfApi

    api = HfApi(token=token)
    api.create_repo(repo, exist_ok=True)
    info = api.upload_folder(
        folder_path=str(out),
        repo_id=repo,
        ignore_patterns=["pack/*"],
        commit_message="Fine-tuned checkpoint from gutcheck finetune",
    )
    return info.oid
