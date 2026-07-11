"""Golden-file regression tests: full pipeline output pinned per fixture.

Regenerate with: python tools/regen_goldens.py
"""

import json
import pathlib

import pytest

from rent_analyzer.analyze import analyze_agreement

ROOT = pathlib.Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"
GOLDEN = ROOT / "tests" / "golden"

CASES = sorted(path.stem for path in FIXTURES.glob("*.txt"))


@pytest.mark.parametrize("name", CASES)
def test_golden(name):
    text = (FIXTURES / f"{name}.txt").read_text(encoding="utf-8")
    expected = json.loads((GOLDEN / f"{name}.json").read_text(encoding="utf-8"))
    actual = analyze_agreement(text)
    assert actual == expected, f"Golden mismatch for {name}"
