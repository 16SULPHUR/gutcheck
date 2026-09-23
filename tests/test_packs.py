import json

import pytest

from gutcheck.packs import PackError, load_packs, resolve
from tests.packs import TOY_PACK, write_toy_pack


def test_bundled_prompt_guard():
    pack = load_packs()["prompt-guard"]
    assert set(pack.questions) == {"injection", "jailbreak"}
    q = pack.questions["injection"]
    assert set(q.payload()) == {"type", "instructions", "criteria"}
    assert set(q.criteria) == {"true", "false"}
    assert q.eval.labels == {"1": True, "0": False}


def test_extra_dir_pack_with_calibration(tmp_path):
    d = write_toy_pack(tmp_path)
    (d / "calibration.json").write_text(json.dumps({"temperatures": {"bad": 1.7, "gone": 2}}))
    pack = load_packs([str(tmp_path)])["toy"]
    assert pack.directory == d
    assert pack.temperatures == {"bad": 1.7}
    assert pack.baseline is None
    assert pack.questions["bad"].label_index(True) == 1


def test_resolve():
    packs = load_packs()
    assert resolve(packs, "prompt-guard").id == "prompt-guard"
    assert resolve(packs, "prompt-guard@1").version == 1
    with pytest.raises(PackError, match="version 1"):
        resolve(packs, "prompt-guard@7")
    with pytest.raises(PackError, match="unknown pack"):
        resolve(packs, "nope")


def test_invalid_pack(tmp_path):
    write_toy_pack(tmp_path, TOY_PACK.replace("type: noul", "type: maybe"))
    with pytest.raises(PackError, match="invalid pack"):
        load_packs([str(tmp_path)])


def test_choice_label_index(tmp_path):
    write_toy_pack(
        tmp_path,
        TOY_PACK.replace("type: noul", "type: choice").replace(
            '{"yes": true, "no": false}', '{"yes": true, "no": "false"}'
        ),
    )
    q = load_packs([str(tmp_path)])["toy"].questions["bad"]
    assert q.label_index("false") == 1
    with pytest.raises(PackError):
        q.label_index("maybe")
