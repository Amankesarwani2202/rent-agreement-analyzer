"""Plain-text summary report generation (English legacy + localized)."""

from rent_analyzer import i18n


def generate_localized_report(analysis, lang="en"):
    """Downloadable text report in any supported language."""
    lines = []
    title = i18n.t("app_title", lang).upper()
    lines.append(title)
    lines.append("=" * max(24, len(title)))
    lines.append("")
    lines.append(f"{i18n.t('risk_score', lang)}: {analysis['score']}/100")
    lines.append(f"{i18n.t('overall_risk', lang)}: {i18n.band_text(analysis['band'], lang)}")
    lines.append("")

    lines.append(i18n.t("key_terms_tab", lang).upper())
    key_terms = analysis["key_terms"]
    not_found = i18n.key_term_label("not_found", lang)
    for key in ("rent", "deposit", "lease_term", "notice_period", "payment_due"):
        value = key_terms.get(key) or ""
        if value == "Not clearly found":
            value = not_found
        lines.append(f"- {i18n.key_term_label(key, lang)}: {value}")
    lines.append("")

    lines.append(i18n.t("risks_tab", lang).upper())
    flags = analysis["risk_flags"]
    if flags:
        for flag in flags:
            severity = i18n.severity_text(flag["severity"], lang)
            category = i18n.category_text(flag["category"], lang)
            reason = i18n.reason_text(flag.get("reason_key"), lang, flag.get("reason", ""))
            lines.append(f"- [{severity}] {category}: {reason}")
            if flag.get("clause"):
                lines.append(f"  > {flag['clause'][:220]}")
    else:
        lines.append(f"- {i18n.t('no_risks', lang)}")
    lines.append("")

    severities = {flag["severity"] for flag in flags}
    if "severe" in severities:
        kind = "severe"
    elif "moderate" in severities:
        kind = "moderate"
    elif severities:
        kind = "mild"
    else:
        kind = "clean"
    lines.append(i18n.summary_paragraph(kind, lang))
    lines.append("")
    lines.append(i18n.t("disclaimer", lang))
    return "\n".join(lines)


def format_list(values, limit=5):
    if not values:
        return "Not clearly found"
    return ", ".join(values[:limit])


def generate_summary(text, entities, key_terms, clauses, risks, score, band):
    lines = []
    lines.append("RENT AGREEMENT SUMMARY")
    lines.append("=" * 24)
    lines.append("")
    lines.append("1) QUICK ASSESSMENT")
    lines.append(f"- Agreement risk score: {score}/100")
    lines.append(f"- Risk level: {band}")
    lines.append(f"- Total words reviewed: {len(text.split())}")
    lines.append(f"- Potential risk clauses found: {len(risks)}")
    lines.append("")
    lines.append("2) KEY TERMS")
    for key, value in key_terms.items():
        lines.append(f"- {key}: {value}")
    lines.append("")
    lines.append("3) PARTIES & CORE ENTITIES")
    lines.append(f"- People: {format_list(entities.get('People', []), 6)}")
    lines.append(f"- Organizations: {format_list(entities.get('Organizations', []), 6)}")
    lines.append(f"- Locations: {format_list(entities.get('Locations', []), 6)}")
    lines.append(f"- Dates: {format_list(entities.get('Dates', []), 8)}")
    lines.append(f"- Money references: {format_list(entities.get('Money', []), 8)}")
    lines.append("")
    lines.append("4) IMPORTANT CLAUSES")
    if clauses:
        for clause in clauses:
            lines.append(f"- {clause}")
    else:
        lines.append("- No clear clause sentences identified.")
    lines.append("")
    lines.append("5) RISK NOTES")
    if risks:
        for risk in risks:
            label = risk.get("term") or risk.get("category") or "risk"
            reason = risk.get("why") or risk.get("reason") or "Review this clause carefully."
            evidence = risk.get("evidence") or risk.get("clause") or ""
            lines.append(f"- [{risk['severity']}] {str(label).title()} | Why: {reason}")
            if evidence:
                lines.append(f"  Evidence: {evidence[:220]}")
    else:
        lines.append("- No major suspicious terms from the configured risk list.")
    lines.append("")
    lines.append("6) DISCLAIMER")
    lines.append("- This is an automated document review, not legal advice.")
    lines.append("- Validate key clauses with the signed agreement and local tenancy laws.")

    return "\n".join(lines)
