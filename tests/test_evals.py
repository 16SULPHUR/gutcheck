import json

import pytest

from gutcheck import evals
from gutcheck.config import Thresholds
from gutcheck.packs import Pack, load_packs
from tests.packs import ToyEngine, write_toy_pack


@pytest.fixture
def toy(tmp_path):
    write_toy_pack(tmp_path)
    return load_packs([str(tmp_path)])["toy"]


def test_metrics_on_toy_pack(toy):
    report = evals.evaluate_pack(ToyEngine(), toy, Thresholds(), log=lambda _: None)
    raw = report["questions"]["bad"]["raw"]
    assert raw["n"] == 18
    assert raw["accuracy"] == pytest.approx(16 / 18, abs=1e-4)
    assert raw["precision"] == pytest.approx(8 / 9, abs=1e-4)
    assert raw["recall"] == pytest.approx(8 / 9, abs=1e-4)
    assert raw["act_rate"] == 1.0
    assert raw["ece"] == pytest.approx(0.95 - 16 / 18, abs=1e-3)
    assert report["questions"]["bad"]["models"] == {"english": 18}
    assert report["questions"]["bad"]["dataset"]["commit"] is None
    assert report["temperatures"] == {}


def test_calibration_improves_ece(toy):
    engine = ToyEngine()
    report = evals.evaluate_pack(engine, toy, Thresholds(), calibrate=True, log=lambda _: None)
    q = report["questions"]["bad"]
    assert engine.calls == 36
    assert q["temperature"] > 1
    assert q["calibrated"]["ece"] < q["raw"]["ece"]
    assert q["calibrated"]["accuracy"] == q["raw"]["accuracy"]


def test_max_rows_subsamples(toy):
    toy.questions["bad"].eval.max_rows = 5
    report = evals.evaluate_pack(ToyEngine(), toy, Thresholds(), log=lambda _: None)
    assert report["questions"]["bad"]["raw"]["n"] == 5


def test_unmapped_label(toy):
    del toy.questions["bad"].eval.labels["no"]
    with pytest.raises(ValueError, match="no mapping"):
        evals.evaluate_pack(ToyEngine(), toy, Thresholds(), log=lambda _: None)


def test_check_against_baseline(toy):
    report = evals.evaluate_pack(ToyEngine(), toy, Thresholds(), log=lambda _: None)
    assert evals.check(report, None) == ["no committed baseline (eval.json)"]
    assert evals.check(report, report) == []

    worse = json.loads(json.dumps(report))
    worse["questions"]["bad"]["calibrated"]["accuracy"] -= 0.1
    worse["questions"]["bad"]["calibrated"]["ece"] += 0.1
    problems = evals.check(worse, report)
    assert len(problems) == 2
    assert evals.check(report, {"questions": {}}) == ["bad: not in the baseline"]


def test_write_outputs_round_trip(toy):
    report = evals.evaluate_pack(ToyEngine(), toy, Thresholds(), calibrate=True, log=lambda _: None)
    evals.write_outputs(report, toy, calibrated=True)
    reloaded = Pack.load(toy.directory)
    assert reloaded.baseline == report
    assert reloaded.temperatures == report["temperatures"]
    md = (toy.directory / "EVAL.md").read_text()
    assert "# toy v2: evaluation" in md
    assert "| Accuracy |" in md


def test_render_summary(toy):
    report = evals.evaluate_pack(ToyEngine(), toy, Thresholds(), log=lambda _: None)
    summary = evals.render_summary(report, toy, ["no committed baseline (eval.json)"], True)
    assert summary.startswith("## toy v2")
    assert "❌ no committed baseline" in summary
    assert "<code>toy/eval.json</code>" in summary
    assert "<code>toy/calibration.json</code>" in summary


def test_read_records_csv(tmp_path):
    path = tmp_path / "d.csv"
    path.write_text("prompt,type\nhello,benign\n")
    assert evals.read_records(path) == [{"prompt": "hello", "type": "benign"}]
    with pytest.raises(ValueError, match="unsupported"):
        evals.read_records(tmp_path / "d.xlsx")


def test_read_records_parquet(tmp_path):
    pa = pytest.importorskip("pyarrow")
    import pyarrow.parquet as pq

    path = tmp_path / "d.parquet"
    pq.write_table(pa.table({"text": ["hi"], "label": [1]}), path)
    assert evals.read_records(path) == [{"text": "hi", "label": 1}]
