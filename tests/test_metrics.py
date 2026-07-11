"""Metrics regression gate: the analyzer must keep near-perfect scores on
the synthetic corpus. If a change drops recall or precision below the
baseline, this test fails - fix the rule, don't lower the bar."""

from testgen.evaluate import evaluate

BASELINE_RECALL = 0.99
BASELINE_PRECISION = 0.99


def test_synthetic_corpus_metrics():
    result = evaluate(n=80, seed=42)
    assert result["recall"] >= BASELINE_RECALL, f"recall regressed: {result['recall']:.3f}"
    assert result["precision"] >= BASELINE_PRECISION, f"precision regressed: {result['precision']:.3f}"


def test_held_out_seed_metrics():
    # Seed never used while tuning rules - guards against overfitting.
    result = evaluate(n=80, seed=20260707)
    assert result["recall"] >= BASELINE_RECALL
    assert result["precision"] >= BASELINE_PRECISION
