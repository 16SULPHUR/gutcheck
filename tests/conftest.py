import os

import pytest


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for key in list(os.environ):
        if key.startswith("GUTCHECK_"):
            monkeypatch.delenv(key)
