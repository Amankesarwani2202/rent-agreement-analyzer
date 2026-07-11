"""Synthetic rent agreement generator with ground-truth labels.

Each generated document = list of labeled clauses:
  {"text": ..., "category": ..., "kind": "safe"|"trap"|"neutral"|"rent",
   "expect": [categories that MUST flag for this clause]}

plus document-level ground truth (expected flag categories, key terms).
"""

import random

from testgen.clause_bank import (
    ADDRESSES,
    CLAUSE_BANK,
    HEADERS,
    NAMES_L,
    NAMES_T,
    NEUTRAL_CLAUSES,
    PARTY_SYNONYMS,
    POOLS,
    RECITALS,
    RENT_CLAUSES,
)


def fill(template, rng, parties):
    landlord, tenant = parties
    out = template.replace("{L}", landlord).replace("{T}", tenant)
    for key, pool in POOLS.items():
        placeholder = "{" + key + "}"
        while placeholder in out:
            out = out.replace(placeholder, rng.choice(pool), 1)
    return out


def generate_document(rng, trap_probability=0.5):
    parties = rng.choice(PARTY_SYNONYMS)
    landlord_name = rng.choice(NAMES_L)
    tenant_name = rng.choice(NAMES_T)
    address = rng.choice(ADDRESSES)

    clauses = []

    rent_template, _ = rng.choice(RENT_CLAUSES)
    clauses.append({"text": fill(rent_template, rng, parties), "category": "rent", "kind": "rent", "expect": []})

    for category, variants in CLAUSE_BANK.items():
        is_trap = rng.random() < trap_probability
        if is_trap:
            chosen = rng.choice(variants["trap"])
            clauses.append(
                {
                    "text": fill(chosen["text"], rng, parties),
                    "category": category,
                    "kind": "trap",
                    "expect": list(chosen["expect"]),
                }
            )
        else:
            template = rng.choice(variants["safe"])
            clauses.append({"text": fill(template, rng, parties), "category": category, "kind": "safe", "expect": []})

    for template in rng.sample(NEUTRAL_CLAUSES, k=rng.randint(2, 4)):
        clauses.append({"text": fill(template, rng, parties), "category": "neutral", "kind": "neutral", "expect": []})

    rng.shuffle(clauses)

    header = rng.choice(HEADERS)
    recital = fill(
        rng.choice(RECITALS).replace("{landlord_name}", landlord_name).replace("{tenant_name}", tenant_name).replace("{address}", address),
        rng,
        parties,
    )

    numbered = [f"{i + 1}. {clause['text']}" for i, clause in enumerate(clauses)]
    text = header + "\n\n" + recital + "\n\n" + "\n".join(numbered)

    expected = set()
    for clause in clauses:
        expected.update(clause["expect"])

    return {
        "text": text,
        "clauses": clauses,
        "expected_flags": sorted(expected),
        "parties": parties,
    }


def generate_corpus(n, seed=42, trap_probability=0.5):
    rng = random.Random(seed)
    return [generate_document(rng, trap_probability) for _ in range(n)]
