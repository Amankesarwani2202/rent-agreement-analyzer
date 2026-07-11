"""Regenerate golden files for tests/test_golden.py.

Usage: python tools/regen_goldens.py
Forces the no-spaCy fallback path so goldens are environment-independent.
"""

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from rent_analyzer import preprocess  # noqa: E402

preprocess.get_nlp = lambda: None

from rent_analyzer.analyze import analyze_agreement  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures"
GOLDEN = ROOT / "tests" / "golden"
GOLDEN.mkdir(exist_ok=True)


def main():
    for fixture in sorted(FIXTURES.glob("*.txt")):
        text = fixture.read_text(encoding="utf-8")
        result = analyze_agreement(text)
        out = GOLDEN / f"{fixture.stem}.json"
        out.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"wrote {out.relative_to(ROOT)}  (score={result['score']}, band={result['band']}, flags={len(result['risk_flags'])})")


if __name__ == "__main__":
    main()
