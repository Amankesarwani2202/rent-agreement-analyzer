"""Top-level analysis pipeline and scoring."""

from rent_analyzer.facts import extract_currency, extract_key_terms
from rent_analyzer.preprocess import extract_entities, preprocess_text, split_sentences
from rent_analyzer.rules import JURISDICTION_RULES, classify_clauses, infer_jurisdiction

SEVERITY_POINTS = {"mild": 8, "moderate": 16, "severe": 24}


def score_flags(risk_flags):
    score = 100
    severity_counts = {"none": 0, "mild": 0, "moderate": 0, "severe": 0}
    for flag in risk_flags:
        severity_counts[flag["severity"]] += 1
        score -= SEVERITY_POINTS.get(flag["severity"], 0)
    score = max(0, score)

    if severity_counts["severe"]:
        band = "High"
    elif severity_counts["moderate"] or severity_counts["mild"] >= 2:
        band = "Medium"
    else:
        band = "Low"

    return score, band, severity_counts


def summarize_flags(risk_flags):
    if risk_flags:
        if any(flag["severity"] == "severe" for flag in risk_flags):
            return (
                "This lease contains several clauses that appear one-sided or potentially unlawful. "
                "The strongest concerns are around fees, notice rights, eviction, and repair obligations, and those terms should be revised before signing."
            )
        if any(flag["severity"] == "moderate" for flag in risk_flags):
            return (
                "This lease has a few advisory concerns that should be reviewed before signing. "
                "The main issues are around notice periods, deposit handling, or dispute rights, but they are not as severe as the most problematic leases."
            )
        return (
            "This lease has a few mild concerns that are worth reviewing. "
            "They appear more advisory than unlawful, but the terms should still be clarified to avoid later disputes."
        )
    return (
        "This lease appears broadly fair and tenant-friendly. "
        "The core terms around rent, deposit, notice, and fees look balanced and do not show obvious illegal or unusually one-sided clauses."
    )


def analyze_agreement(text, jurisdiction=None):
    processed_text, _ = preprocess_text(text)
    sentences = split_sentences(processed_text)
    jurisdiction_code = infer_jurisdiction(processed_text, jurisdiction)
    rules = JURISDICTION_RULES.get(jurisdiction_code, JURISDICTION_RULES["DEFAULT"])
    entities = extract_entities(processed_text)
    key_terms = extract_key_terms(processed_text)
    risk_flags = classify_clauses(sentences, jurisdiction_code)
    score, band, _ = score_flags(risk_flags)

    return {
        "jurisdiction": jurisdiction_code,
        "jurisdiction_rules": rules,
        "key_terms": {
            "rent": extract_currency(key_terms.get("Monthly Rent", "")) or key_terms.get("Monthly Rent"),
            "deposit": extract_currency(key_terms.get("Security Deposit", "")) or key_terms.get("Security Deposit"),
            "lease_term": key_terms.get("Lease Term"),
            "notice_period": key_terms.get("Notice Period"),
            "payment_due": key_terms.get("Payment Due"),
            "deposit_refundable": True,
        },
        "key_terms_raw": key_terms,
        "risk_flags": risk_flags,
        "summary": summarize_flags(risk_flags),
        "score": score,
        "band": band,
        "entities": entities,
        "sentences": sentences,
    }
