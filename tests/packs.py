import json
from pathlib import Path

TOY_PACK = """\
id: toy
version: 2
description: Spots the word bad.
questions:
  bad:
    type: noul
    instructions: Does the text contain the word bad?
    criteria: {true: it does, false: it does not}
    eval:
      test: {path: test.jsonl, license: CC0-1.0}
      calibration: {path: train.jsonl, license: CC0-1.0}
      text_field: text
      label_field: label
      labels: {"yes": true, "no": false}
"""


def write_toy_pack(root: Path, pack_yaml: str = TOY_PACK) -> Path:
    d = root / "toy"
    d.mkdir(parents=True)
    (d / "pack.yaml").write_text(pack_yaml)
    rows = [{"text": f"bad {i}", "label": "yes"} for i in range(8)]
    rows += [{"text": f"good {i}", "label": "no"} for i in range(8)]
    rows += [{"text": "bad but fine", "label": "no"}, {"text": "sneaky", "label": "yes"}]
    for name in ("test.jsonl", "train.jsonl"):
        (d / name).write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    return d


class ToyEngine:
    """Says yes (p=0.95) whenever the text contains "bad"."""

    backend = "toy"

    def __init__(self):
        self.calls = 0

    def start(self):
        pass

    def predict(self, state, questions, model=None):
        self.calls += 1
        p = 0.95 if "bad" in state else 0.05
        answers = {qid: {"type": "noul", "noul": p, "confidence": 0.95} for qid in questions}
        return {"answers": answers, "routing": {"model": "english", "reason": "test"}}

    def loaded(self):
        return ["english"]

    def close(self):
        pass
