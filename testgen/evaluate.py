"""Evaluation harness: generate labeled agreements, run the analyzer,
report per-category precision/recall and dump failures.

Usage:
    python -m testgen.evaluate --n 200 --seed 42
    python -m testgen.evaluate --n 200 --failures 20   # show failure details
"""

import argparse
import json
import pathlib
import sys
from collections import defaultdict

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from rent_analyzer import preprocess  # noqa: E402

preprocess.get_nlp = lambda: None  # deterministic, env-independent

from rent_analyzer.analyze import analyze_agreement  # noqa: E402
from testgen.generator import generate_corpus  # noqa: E402


def match_flag_to_clause(flag, clauses):
    """Attribute a fired flag back to the generated clause it quotes."""
    flag_clause = flag.get("clause", "").strip().lower()
    for clause in clauses:
        text = clause["text"].strip().lower()
        if text and (text in flag_clause or flag_clause in text):
            return clause
    return None


def evaluate(n=200, seed=42, show_failures=0, trap_probability=0.5):
    corpus = generate_corpus(n, seed=seed, trap_probability=trap_probability)

    tp = defaultdict(int)
    fn = defaultdict(int)
    fp = defaultdict(int)
    failures = []

    for doc_index, doc in enumerate(corpus):
        analysis = analyze_agreement(doc["text"])
        fired = analysis["risk_flags"]

        # For each trap clause: every expected category must have >= 1 flag
        # attributed to that clause.
        for clause in doc["clauses"]:
            attributed = [flag for flag in fired if match_flag_to_clause(flag, [clause])]
            attributed_categories = {flag["category"] for flag in attributed}

            for expected_category in clause["expect"]:
                if expected_category in attributed_categories:
                    tp[expected_category] += 1
                else:
                    fn[expected_category] += 1
                    failures.append(
                        {
                            "type": "MISS",
                            "doc": doc_index,
                            "category": expected_category,
                            "clause": clause["text"],
                            "fired_instead": sorted(attributed_categories),
                        }
                    )

            if clause["kind"] in ("safe", "neutral", "rent"):
                for flag in attributed:
                    fp[flag["category"]] += 1
                    failures.append(
                        {
                            "type": "FALSE_FLAG",
                            "doc": doc_index,
                            "category": flag["category"],
                            "severity": flag["severity"],
                            "clause": clause["text"],
                            "reason": flag["reason"],
                        }
                    )

    categories = sorted(set(list(tp) + list(fn) + list(fp)))
    print(f"\n=== Evaluation: {n} docs, seed {seed} ===\n")
    print(f"{'category':<22} {'TP':>4} {'FN':>4} {'FP':>4} {'recall':>7} {'precision':>9}")
    total_tp = total_fn = total_fp = 0
    for category in categories:
        t, f_, p = tp[category], fn[category], fp[category]
        total_tp += t
        total_fn += f_
        total_fp += p
        recall = t / (t + f_) if (t + f_) else float("nan")
        precision = t / (t + p) if (t + p) else float("nan")
        print(f"{category:<22} {t:>4} {f_:>4} {p:>4} {recall:>7.2f} {precision:>9.2f}")

    overall_recall = total_tp / (total_tp + total_fn) if (total_tp + total_fn) else 0
    overall_precision = total_tp / (total_tp + total_fp) if (total_tp + total_fp) else 0
    print(f"\n{'OVERALL':<22} {total_tp:>4} {total_fn:>4} {total_fp:>4} {overall_recall:>7.2f} {overall_precision:>9.2f}")

    misses = [f for f in failures if f["type"] == "MISS"]
    false_flags = [f for f in failures if f["type"] == "FALSE_FLAG"]
    print(f"\nMisses: {len(misses)}   False flags: {len(false_flags)}")

    if show_failures:
        print("\n=== Sample failures ===")
        seen = set()
        shown = 0
        for failure in failures:
            key = (failure["type"], failure["category"], failure["clause"][:60])
            if key in seen:
                continue
            seen.add(key)
            print(f"\n[{failure['type']}] {failure['category']}")
            print(f"  clause: {failure['clause'][:160]}")
            if failure["type"] == "MISS":
                print(f"  fired instead: {failure['fired_instead']}")
            else:
                print(f"  reason: {failure.get('reason', '')[:120]}")
            shown += 1
            if shown >= show_failures:
                break

    return {
        "recall": overall_recall,
        "precision": overall_precision,
        "misses": len(misses),
        "false_flags": len(false_flags),
        "per_category": {c: {"tp": tp[c], "fn": fn[c], "fp": fp[c]} for c in categories},
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=200)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--failures", type=int, default=0)
    parser.add_argument("--json", type=str, default="")
    args = parser.parse_args()
    result = evaluate(args.n, args.seed, args.failures)
    if args.json:
        pathlib.Path(args.json).write_text(json.dumps(result, indent=2))
