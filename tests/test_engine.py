import pytest

from gutcheck.engine import resolve_model


@pytest.mark.parametrize(
    ("model", "expected"),
    [
        (None, None),
        ("", None),
        ("english", "english"),
        ("Multilingual", "multilingual"),
        ("ml", "multilingual"),
        ("convaiinnovations/laya-typed-decisions", "typed-decisions"),
        ("convaiinnovations/laya", None),
        ("jev-latest", None),
    ],
)
def test_resolve_model(model, expected):
    assert resolve_model(model) == expected


def test_engine_preloads_configured_models(engine, agents):
    engine.start()
    assert engine.loaded() == ["english", "multilingual"]
