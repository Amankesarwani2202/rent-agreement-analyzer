"""Clause risk rules v2: actor attribution, negation handling, and
normalized quantities (see ROBUSTNESS_PLAN.md sections 3.4-3.6).

Key differences from v1:
- Who does what matters: "Landlord is responsible for structural repairs" is
  safe; the same words with Tenant as the obligated party is a trap.
- Negation matters: "shall NOT enter without notice" and "NO penalty shall
  apply" are safe.
- Amounts/durations are parsed via rent_analyzer.normalize (digits, words,
  Rs./INR/₹/$, 'sixty (60) days'), with currency-aware thresholds.
"""

import re

from rent_analyzer.normalize import duration_near, months_of_rent, parse_durations, parse_money

JURISDICTION_RULES = {
    "DEFAULT": {
        "entry_notice_required": False,
        "rent_increase_notice_days_min": 30,
        "eviction_notice_days_min": 7,
        "eviction_requires_just_cause": False,
        "deposit_must_be_refundable": True,
        "deposit_max_months": 3,
        "late_fee_threshold_usd": 100,
        "late_fee_threshold_inr": 1000,
        "repair_liability_allowed": False,
        "arbitration_neutrality_required": False,
        "renewal_notice_days_max": 30,
        "guest_policy_min_nights": 3,
        "deposit_return_days_max": 45,
    },
    "US-CA": {
        "entry_notice_required": True,
        "rent_increase_notice_days_min": 30,
        "eviction_notice_days_min": 3,
        "eviction_requires_just_cause": True,
        "deposit_must_be_refundable": True,
        "deposit_max_months": 2,
        "late_fee_threshold_usd": 100,
        "late_fee_threshold_inr": 1000,
        "repair_liability_allowed": False,
        "arbitration_neutrality_required": True,
        "renewal_notice_days_max": 30,
        "guest_policy_min_nights": 3,
        "deposit_return_days_max": 21,
        "entry_notice_reference": "CA Civil Code § 1954",
        "eviction_reference": "CA just-cause eviction requirements",
        "deposit_reference": "CA Civil Code § 1950.5 (deposit rules)",
    },
    "US-TX": {
        "entry_notice_required": False,
        "rent_increase_notice_days_min": 30,
        "eviction_notice_days_min": 3,
        "eviction_requires_just_cause": False,
        "deposit_must_be_refundable": True,
        "deposit_max_months": 3,
        "late_fee_threshold_usd": 100,
        "late_fee_threshold_inr": 1000,
        "repair_liability_allowed": False,
        "arbitration_neutrality_required": False,
        "renewal_notice_days_max": 30,
        "guest_policy_min_nights": 3,
        "deposit_return_days_max": 30,
        "deposit_reference": "TX Property Code § 92.103 (deposit return)",
    },
    "IN-MH": {
        "entry_notice_required": True,
        "rent_increase_notice_days_min": 30,
        "eviction_notice_days_min": 15,
        "eviction_requires_just_cause": False,
        "deposit_must_be_refundable": True,
        "deposit_max_months": 6,
        "late_fee_threshold_usd": 100,
        "late_fee_threshold_inr": 1000,
        "repair_liability_allowed": False,
        "arbitration_neutrality_required": False,
        "renewal_notice_days_max": 30,
        "guest_policy_min_nights": 3,
        "deposit_return_days_max": 30,
        "law_reference": "Maharashtra Rent Control Act / Model Tenancy norms",
    },
    "IN-DL": {
        "entry_notice_required": True,
        "rent_increase_notice_days_min": 30,
        "eviction_notice_days_min": 15,
        "eviction_requires_just_cause": True,
        "deposit_must_be_refundable": True,
        "deposit_max_months": 3,
        "late_fee_threshold_usd": 100,
        "late_fee_threshold_inr": 1000,
        "repair_liability_allowed": False,
        "arbitration_neutrality_required": True,
        "renewal_notice_days_max": 30,
        "guest_policy_min_nights": 3,
        "deposit_return_days_max": 30,
        "entry_notice_reference": "Delhi Rent Control Act notice requirements",
        "eviction_reference": "Delhi Rent Control Act",
        "deposit_reference": "Delhi Rent Control Act deposit rules",
    },
}

LANDLORD_TERMS = ["landlord", "lessor", "licensor", "owner", "landlady"]
TENANT_TERMS = ["tenant", "lessee", "licensee", "renter", "occupant"]


def first_party(sentence_lower):
    """Which party appears first in the sentence - a cheap but effective
    proxy for the obligated/acting party in lease drafting."""
    best = None
    best_index = None
    for term in LANDLORD_TERMS:
        index = sentence_lower.find(term)
        if index != -1 and (best_index is None or index < best_index):
            best, best_index = "landlord", index
    for term in TENANT_TERMS:
        index = sentence_lower.find(term)
        if index != -1 and (best_index is None or index < best_index):
            best, best_index = "tenant", index
    return best


def party_near(sentence_lower, keyword, window=80):
    """Party term nearest to a keyword occurrence, within a window."""
    positions = [match.start() for match in re.finditer(re.escape(keyword), sentence_lower)]
    if not positions:
        return None
    best = None
    best_distance = None
    for party, terms in (("landlord", LANDLORD_TERMS), ("tenant", TENANT_TERMS)):
        for term in terms:
            for match in re.finditer(re.escape(term), sentence_lower):
                distance = min(abs(match.start() - p) for p in positions)
                if distance <= window and (best_distance is None or distance < best_distance):
                    best, best_distance = party, distance
    return best


def has_any(text, phrases):
    return any(phrase in text for phrase in phrases)


def landlord_term_pattern():
    return r"(?:" + "|".join(LANDLORD_TERMS) + r")"


def tenant_term_pattern():
    return r"(?:" + "|".join(TENANT_TERMS) + r")"


# --------------------------------------------------------------------------
# Category rules. Each returns (severity, reason) or None.
# --------------------------------------------------------------------------

def rule_late_fee(text, rules):
    negated = has_any(text, ["no late fee", "waive the late fee", "without any late fee", "shall not charge"])
    if negated:
        return None

    monies = parse_money(text)
    amount = monies[0] if monies else None
    per_day = has_any(text, ["per day", "daily", "per diem", "for each day"])
    has_grace = "grace" in text
    uncapped = has_any(text, ["without any grace", "without grace", "no grace"])

    threshold = None
    excessive = False
    if amount:
        threshold = rules["late_fee_threshold_usd"] if amount["currency"] == "USD" else rules["late_fee_threshold_inr"]
        excessive = amount["value"] >= threshold

    if per_day:
        return ("severe", "The late fee accrues per day, which compounds quickly and is a classic unenforceable-penalty pattern.", "late_fee_per_day")
    if excessive and (uncapped or not has_grace):
        return ("severe", "The late fee is unusually high with no grace period, and may be unenforceable.", "late_fee_high_no_grace")
    if excessive:
        return ("moderate", "The late fee is on the high side; confirm the grace period and that the amount is a genuine pre-estimate of loss.", "late_fee_high")
    if amount and not has_grace and uncapped:
        return ("moderate", "The late fee has no grace period; a reasonable grace period is standard.", "late_fee_no_grace")
    return None


def rule_deposit(text, rules):
    nonrefundable = has_any(
        text,
        [
            "non-refundable",
            "nonrefundable",
            "non refundable",
            "shall not be returned",
            "will not be returned",
            "not be refunded",
            "in no event be refunded",
            "in no event be returned",
            "shall be retained by",
            "under no circumstances shall the deposit",
        ],
    )
    if nonrefundable:
        return ("severe", "The deposit is effectively non-refundable; deposits must generally be refundable by law.", "deposit_nonrefundable")

    full_forfeiture = has_any(text, ["forfeited in full", "stand forfeited", "forfeit the entire", "forfeited entirely", "shall be forfeited"])
    if full_forfeiture and not has_any(text, ["shall not be forfeited", "no forfeiture"]):
        return ("severe", "The clause forfeits the entire deposit on early exit regardless of actual loss - a punitive pattern.", "deposit_forfeiture")

    multiple = months_of_rent(text)
    if multiple is not None and ("deposit" in text) and multiple > rules["deposit_max_months"]:
        return (
            "severe",
            f"The deposit equals {multiple} months' rent, above the {rules['deposit_max_months']}-month norm for this jurisdiction.",
            "deposit_excessive",
        )

    if has_any(text, ["return", "refund"]):
        days = duration_near(text, ["return", "refund", "vacat", "handover"], allowed_units={"hour", "day", "week"})
        if days is not None and days > rules["deposit_return_days_max"]:
            return ("moderate", f"The deposit return window ({int(days)} days) exceeds the {rules['deposit_return_days_max']}-day norm.", "deposit_slow_return")

    if "forfeit" in text:
        return ("mild", "The clause allows partial forfeiture of the deposit; check it is limited to actual, documented loss.", "deposit_partial_forfeit")
    return None


def rule_entry(text, rules):
    prohibitive = re.search(r"(?:shall|will|may)\s+not\s+(?:enter|access)", text) or has_any(
        text, ["no entry without", "not enter the premises without"]
    )
    if prohibitive:
        return None  # landlord is being restricted - that protects the tenant

    entry_verb = has_any(text, ["enter", "entry", "access", "master key", "inspect the premises"])
    if not entry_verb:
        return None

    broad = has_any(
        text,
        [
            "without notice",
            "without prior notice",
            "without any notice",
            "at any time",
            "at any hour",
            "any hour",
            "day or night",
            "all hours",
            "sole discretion",
            "absolute discretion",
            "without any intimation",
            "without intimation",
            "without informing",
            "master key",
            "any other purpose",
        ],
    )
    if broad:
        return ("severe", "The entry clause lets the landlord enter without effective notice limits, violating standard notice requirements.", "entry_broad")
    return None


def rule_eviction(text, rules):
    # Self-help eviction: no keyword like "evict" needed.
    self_help = has_any(
        text,
        [
            "lock the premises",
            "change the locks",
            "lockout",
            "disconnect utilities",
            "disconnect the utilities",
            "disconnect electricity",
            "remove the belongings",
            "remove the tenant's belongings",
            "without recourse to court",
            "without recourse to a court",
        ],
    )
    if self_help:
        return ("severe", "The clause permits self-help eviction (lockout, utility disconnection, or removing belongings) without court process - unlawful nearly everywhere.", "eviction_self_help")

    termination_context = has_any(text, ["evict", "vacate", "terminate", "termination", "quit and deliver", "vacant possession"])
    if not termination_context:
        return None

    # A deposit-return clause mentioning "handover of vacant possession" is
    # about the deposit timeline, not eviction.
    if "deposit" in text and has_any(text, ["return", "refund"]) and not has_any(text, ["evict", "terminate"]):
        return None

    if has_any(text, ["shall not terminate", "may not terminate", "shall not evict"]):
        return None

    arbitrary = has_any(text, ["for any reason", "any reason whatsoever", "sole discretion", "absolute discretion", "at any time", "without assigning any reason", "without cause"])
    immediate = has_any(text, ["vacate immediately", "immediately vacate", "forthwith"])
    days = duration_near(text, ["notice", "vacate", "quit", "terminate", "possession", "within"])
    too_short = days is not None and days < rules["eviction_notice_days_min"]

    if arbitrary or immediate or too_short:
        detail = []
        if arbitrary:
            detail.append("termination at will/sole discretion")
        if immediate:
            detail.append("immediate vacation demanded")
        if too_short:
            detail.append(f"only {round(days, 1)} days notice (minimum here: {rules['eviction_notice_days_min']})")
        return ("severe", "The termination/eviction clause is one-sided: " + "; ".join(detail) + ".", "eviction_one_sided")
    return None


def rule_waiver(text, rules):
    if has_any(text, ["shall not constitute a waiver", "shall not be deemed a waiver", "no waiver of"]):
        return None

    waive_verb = re.search(r"\b(waives?|waiver|relinquish(?:es)?|forgoes?|gives up)\b", text)
    if not waive_verb:
        return None

    actor = party_near(text, waive_verb.group(1)) or first_party(text)
    if actor == "landlord":
        return None  # landlord waiving something is tenant-favorable

    protected = has_any(
        text,
        [
            "jury",
            "counterclaim",
            "rent control",
            "tenant protection",
            "habitability",
            "statutory",
            "all rights",
            "any rights",
            "right to notice",
            "protections available",
            "interest on the deposit",
            "legal remedies",
        ],
    )
    if protected:
        return ("severe", "The tenant is made to waive legal rights or protections; such blanket waivers are typically unenforceable but signal intent.", "waiver_rights")
    return None


def rule_arbitration(text, rules):
    dispute_context = has_any(text, ["arbitrat", "jury", "dispute", "adjudicat"])
    if not dispute_context:
        return None

    one_sided = has_any(
        text,
        [
            "selected solely by",
            "appointed solely by",
            "chosen solely by",
            "sole discretion of the",
            "bear the entire cost",
            "bear all costs of arbitration",
            "waives the right to a jury",
            "waives any right to a jury",
        ],
    )
    if one_sided:
        return ("severe", "The dispute clause is one-sided: the landlord controls the arbitrator selection or the tenant bears all costs.", "arbitration_one_sided")
    return None


def rule_penalty(text, rules):
    if has_any(text, ["no penalty", "without penalty", "shall not be liable for any fine", "neither party shall be liable"]):
        return None

    per_item = re.search(r"(?:penalt\w*|fines?|charges?|deduct\w*|fee)\s[^.\n]{0,40}?per\s+(nail|hole|mark|occurrence|item|violation|infraction|guest)", text) or re.search(
        r"per\s+(nail|hole|mark|occurrence|item|violation|infraction)", text
    )
    penalty_context = re.search(r"\b(penalt(?:y|ies)|fines?)\b", text) or per_item
    if not penalty_context:
        return None
    landlord_determined = has_any(text, ["as determined by the", "at the sole discretion of the", "as the " ]) and party_near(text, "determined") != "tenant"
    monies = parse_money(text)
    threshold = None
    excessive = False
    if monies:
        amount = monies[0]
        threshold = rules["late_fee_threshold_usd"] if amount["currency"] == "USD" else rules["late_fee_threshold_inr"]
        excessive = amount["value"] >= threshold

    if per_item or (excessive and has_any(text, ["deduct", "fine", "penalty"])):
        return ("severe", "Per-item or outsized penalties (e.g. per nail hole) are punitive charges courts rarely enforce - and a strong bad-faith signal.", "penalty_per_item")
    if landlord_determined and has_any(text, ["fine", "penalty"]):
        return ("moderate", "Penalties set unilaterally by the landlord with no stated scale are open to abuse.", "penalty_landlord_set")
    return None


def rule_repairs(text, rules):
    structural = has_any(text, ["structural", "roof", "all repairs", "major repairs", "habitability"])
    as_is = has_any(text, ["as-is", "as is condition", "strictly as-is"])

    if not structural and not as_is:
        return None

    if has_any(text, ["shall not be responsible for structural"]) :
        pass  # falls through to actor check

    # Who bears it?
    anchor = "repair" if "repair" in text else ("habitability" if "habitability" in text else "structural")
    actor = party_near(text, anchor) or first_party(text)
    tenant_burden = actor == "tenant" or re.search(
        r"borne\s+(?:solely\s+)?by\s+the\s+" + tenant_term_pattern(), text
    ) or re.search(tenant_term_pattern() + r"(?:'s)?\s+(?:own\s+)?(?:cost|expense)", text)

    landlord_burden = re.search(
        landlord_term_pattern() + r"\s+(?:is|shall be|will be|remains)\s+responsible", text
    ) or re.search(r"borne\s+(?:solely\s+)?by\s+the\s+" + landlord_term_pattern(), text) or re.search(
        r"carried out by the\s+" + landlord_term_pattern(), text
    ) or re.search(landlord_term_pattern() + r"\s+at\s+(?:his|her|its|their)\s+own\s+cost", text)

    if as_is and has_any(text, ["habitability", "waives", "relinquish"]):
        return ("severe", "The tenant accepts the premises 'as-is' and gives up habitability claims - the landlord's core duty is being shifted away.", "repairs_as_is")

    if landlord_burden and not tenant_burden:
        return None

    if structural and tenant_burden:
        return ("severe", "Structural/major repair obligations are shifted to the tenant; these are legally the landlord's responsibility.", "repairs_tenant_structural")
    return None


def rule_guest_policy(text, rules):
    guest_context = has_any(text, ["guest", "visitor"])
    if not guest_context:
        return None

    prohibitive = re.search(r"\bno\s+guests?\b|\bno\s+guest\s+shall\b|guests?\s+(?:are\s+)?(?:not\s+permitted|prohibited|shall\s+not)", text)
    permission_required = has_any(text, ["prior written permission", "prior written approval", "advance written approval"]) and has_any(text, ["overnight", "stay"])
    nights = duration_near(text, ["stay", "guest", "visitor", "overnight"], max_distance=160)
    too_restrictive = nights is not None and nights <= rules["guest_policy_min_nights"] and has_any(text, ["not", "no more than", "may not", "maximum"])

    if prohibitive or permission_required or too_restrictive:
        return ("moderate", "The guest policy is unusually restrictive (blanket bans or per-stay landlord permission) and intrudes on ordinary quiet enjoyment.", "guest_restrictive")
    return None


def rule_government_contact(text, rules):
    authority_context = has_any(text, ["government", "authority", "authorities", "inspector", "municipal", "rent court", "housing board"])
    if not authority_context:
        return None

    prohibitive = re.search(
        r"(?:shall\s+not|may\s+not|must\s+not|agrees?\s+(?:never\s+)?not\s+to|agrees?\s+never\s+to|prohibited\s+from|refrain\s+from)\s+"
        r"(?:approach|contact|complain|report|notify|file)",
        text,
    )
    retaliation = has_any(text, ["grounds for immediate eviction", "grounds for eviction", "grounds for termination"]) and has_any(
        text, ["contact", "complaint", "approach", "report"]
    )
    if prohibitive or retaliation:
        return ("severe", "The clause punishes lawful complaints to authorities - retaliatory and almost certainly unenforceable, and a serious red flag about the landlord.", "govt_retaliation")
    return None


def rule_renewal(text, rules):
    renewal_context = has_any(text, ["renew", "renewal", "extended", "extension of this"])
    if not renewal_context:
        return None

    automatic = has_any(text, ["automatically renew", "automatic renewal", "shall stand renewed", "auto-renew"])
    sole_discretion = has_any(text, ["sole discretion", "absolute discretion", "solely by the", "determined solely"])

    if sole_discretion:
        return ("moderate", "Renewal (or renewal rent) is at the landlord's sole discretion - the tenant has no predictable right to stay.", "renewal_sole_discretion")

    if automatic:
        days = duration_near(text, ["notice", "non-renewal"])
        if days is not None and days > rules["renewal_notice_days_max"]:
            return (
                "moderate",
                f"Auto-renewal requires {int(days)} days advance notice to escape - an easy trap; {rules['renewal_notice_days_max']} days is the norm.",
                "renewal_auto_long_notice",
            )
        return ("mild", "The lease auto-renews; diarize the notice deadline or you are locked in for another term.", "renewal_auto")
    return None


def rule_rent_increase(text, rules):
    increase_context = has_any(
        text,
        ["rent increase", "increase the rent", "increase in rent", "rent revision", "revise the rent", "escalation", "enhance the rent", "enhancement of rent", "revised rent"],
    ) or re.search(r"rent[^.\n]{0,40}\b(?:revis|increas|enhanc)", text) or re.search(r"\b(?:revis|increas|enhanc)\w*[^.\n]{0,25}\brent\b", text)
    if not increase_context:
        return None

    if has_any(text, ["sole discretion", "absolute discretion", "at any time", "as per market rate", "as determined by the"]):
        return ("severe", "Rent can be raised unilaterally/without objective limits during the tenancy.", "rent_increase_unilateral")

    days = duration_near(text, ["notice"])
    if days is not None and days < rules["rent_increase_notice_days_min"]:
        return ("severe", f"Rent-increase notice of {int(days)} days is below the {rules['rent_increase_notice_days_min']}-day minimum expected here.", "rent_increase_short_notice")
    return None


CATEGORY_RULES = [
    ("late_fee", rule_late_fee, ["late fee", "late fees", "late charge", "delayed payment", "late payment", "daily fine"]),
    ("deposit", rule_deposit, ["deposit", "retained by", "forfeited", "refundable"]),
    ("rent_increase", rule_rent_increase, ["increase", "revision", "revise", "escalation", "enhance", "revised rent"]),
    ("entry", rule_entry, ["enter", "entry", "access", "master key", "inspect"]),
    ("eviction", rule_eviction, ["evict", "vacate", "terminate", "quit", "vacant possession", "lock the premises", "change the locks", "disconnect", "belongings", "recourse to court"]),
    ("waiver", rule_waiver, ["waive", "waiver", "relinquish", "forgo", "gives up"]),
    ("arbitration", rule_arbitration, ["arbitrat", "jury", "dispute"]),
    ("penalty", rule_penalty, ["penalty", "penalties", "fine", "fines", "per nail", "per hole", "per occurrence", "per violation", "per item"]),
    ("renewal", rule_renewal, ["renew", "extension"]),
    ("repairs", rule_repairs, ["repair", "structural", "roof", "habitability", "as-is", "as is"]),
    ("guest_policy", rule_guest_policy, ["guest", "visitor"]),
    ("government_contact", rule_government_contact, ["government", "authority", "authorities", "inspector", "municipal"]),
]


def build_risk_flag(category, clause, jurisdiction, rules, law_reference=None):
    """Evaluate one category rule against one clause. Returns a flag dict or None."""
    rule_fn = next((fn for name, fn, _ in CATEGORY_RULES if name == category), None)
    if rule_fn is None:
        return None
    result = rule_fn(clause.lower(), rules)
    if result is None:
        return None
    severity, reason = result[0], result[1]
    reason_key = result[2] if len(result) > 2 else None
    return {
        "category": category,
        "clause": clause,
        "severity": severity,
        "reason": reason,
        "reason_key": reason_key,
        "law_reference": law_reference
        or rules.get(f"{category}_reference")
        or rules.get("entry_notice_reference")
        or rules.get("law_reference")
        or "Applicable local tenancy law",
    }


def classify_clauses(sentences, jurisdiction):
    rules = JURISDICTION_RULES.get(jurisdiction, JURISDICTION_RULES["DEFAULT"])
    flags = []
    for sentence in sentences:
        text = sentence.lower()
        for category, _, triggers in CATEGORY_RULES:
            if any(trigger in text for trigger in triggers):
                reference = {
                    "deposit": rules.get("deposit_reference"),
                    "entry": rules.get("entry_notice_reference"),
                    "eviction": rules.get("eviction_reference"),
                }.get(category)
                risk = build_risk_flag(category, sentence, jurisdiction, rules, reference)
                if risk:
                    flags.append(risk)

    seen = set()
    unique_flags = []
    for flag in flags:
        signature = (flag["category"], flag["clause"].lower())
        if signature not in seen:
            seen.add(signature)
            unique_flags.append(flag)
    return unique_flags


# Strong signals only: full place names, statute references. Two-letter
# abbreviations are matched only as standalone uppercase tokens.
_JURISDICTION_SIGNALS = {
    "US-CA": [r"\bcalifornia\b", r"\blos angeles\b", r"\bsan francisco\b", r"\bcivil code\b", r"\bCA\b"],
    "US-TX": [r"\btexas\b", r"\baustin\b", r"\bhouston\b", r"\bproperty code\b", r"\bTX\b"],
    "IN-MH": [r"\bmaharashtra\b", r"\bmumbai\b", r"\bpune\b", r"\bleave and licen[cs]e\b"],
    "IN-DL": [r"\bdelhi\b", r"\bnew delhi\b", r"\bdelhi rent control\b"],
}


def infer_jurisdiction(text, jurisdiction=None):
    if jurisdiction:
        return jurisdiction
    scores = {}
    for code, patterns in _JURISDICTION_SIGNALS.items():
        score = 0
        for pattern in patterns:
            flags = 0 if pattern in (r"\bCA\b", r"\bTX\b") else re.IGNORECASE
            score += len(re.findall(pattern, text, flags))
        if score:
            scores[code] = score
    if not scores:
        return "DEFAULT"
    return max(scores, key=scores.get)
