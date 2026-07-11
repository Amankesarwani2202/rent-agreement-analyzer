import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from rent_analyzer import preprocess  # noqa: E402


@pytest.fixture(autouse=True)
def deterministic_nlp(monkeypatch):
    """Force the regex sentence-splitter fallback so results are identical
    with or without spaCy installed."""
    monkeypatch.setattr(preprocess, "get_nlp", lambda: None)


FIXTURES = ROOT / "tests" / "fixtures"
GOLDEN = ROOT / "tests" / "golden"
