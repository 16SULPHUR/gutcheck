import json

import yaml

from gutcheck.evals import Row
from gutcheck.finetune import _write_local_pack, heldout_records, model_card, split
from gutcheck.packs import Pack, load_packs


def test_split_is_seeded_and_disjoint():
    rows = [Row(f"t{i}", i % 2) for i in range(50)]
    train, held = split(rows, 0.2)
    assert len(held) == 10 and len(train) == 40
    assert not {r.state for r in train} & {r.state for r in held}
    assert split(rows, 0.2) == (train, held)


def test_heldout_records_use_the_dataset_format():
    pack = load_packs()["prompt-guard"]
    records = heldout_records(pack.questions["injection"], [Row("a", 1), Row("b", 0)])
    assert records == [{"text": "a", "label": "1"}, {"text": "b", "label": "0"}]
    records = heldout_records(pack.questions["jailbreak"], [Row("c", 1)])
    assert records == [{"prompt": "c", "type": "jailbreak"}]


def test_local_pack_points_at_the_checkpoint(tmp_path):
    pack = load_packs()["prompt-guard"]
    (tmp_path / "heldout").mkdir()
    for qid, q in pack.questions.items():
        recs = heldout_records(q, [Row("x", 1), Row("y", 0)])
        (tmp_path / "heldout" / f"{qid}.jsonl").write_text(
            "\n".join(json.dumps(r) for r in recs) + "\n"
        )
    _write_local_pack(pack, tmp_path)
    local = Pack.load(tmp_path / "pack" / "prompt-guard")
    assert local.version == pack.version + 1
    assert local.checkpoint == f"prompt-guard@{pack.version + 1}"
    assert local.model_source() == str(tmp_path / "pack" / "prompt-guard" / "../..")
    ev = local.questions["injection"].eval
    assert ev.test == pack.questions["injection"].eval.test
    assert ev.calibration.path == "../../heldout/injection.jsonl"
    assert ev.calibration_max_rows is None
    assert ev.train == pack.questions["injection"].eval.train
    raw = yaml.safe_load((tmp_path / "pack" / "prompt-guard" / "pack.yaml").read_text())
    assert raw["questions"]["jailbreak"]["instructions"] == pack.questions["jailbreak"].instructions


def test_model_card():
    pack = load_packs()["prompt-guard"]
    q = {
        "data": {"repo": "deepset/prompt-injections", "path": "d.parquet", "license": "Apache-2.0"},
        "train_rows": 437,
        "heldout_rows": 109,
        "heldout_base": {"accuracy": 0.6},
        "heldout_tuned": {"accuracy": 0.9},
    }
    report = {
        "base": {"repo": "convaiinnovations/laya", "subfolder": None},
        "gutcheck": "0.0.1",
        "questions": {"injection": q},
    }
    card = model_card(pack, report)
    assert card.startswith("---\nlicense: apache-2.0")
    assert "| `prompt-guard.injection` | 437 | 109 | 0.600 | 0.900 |" in card
