from rent_analyzer.rules import JURISDICTION_RULES, build_risk_flag, classify_clauses, infer_jurisdiction

DEFAULT = JURISDICTION_RULES["DEFAULT"]


def flag(category, clause, rules=DEFAULT):
    return build_risk_flag(category, clause, "DEFAULT", rules)


# ---- traps must flag ----

def test_nonrefundable_deposit_severe():
    result = flag("deposit", "The deposit is non-refundable under all circumstances.")
    assert result and result["severity"] == "severe"


def test_deposit_retained_severe():
    result = flag("deposit", "The security deposit of Rs. 30,000/- shall be retained by the Landlord and shall not be returned.")
    assert result and result["severity"] == "severe"


def test_deposit_excessive_multiple_severe():
    result = flag("deposit", "The Lessee shall deposit an amount equivalent to ten months' rent as security deposit.")
    assert result and result["severity"] == "severe"


def test_entry_without_notice_severe():
    result = flag("entry", "The landlord may enter at any time without notice.")
    assert result and result["severity"] == "severe"


def test_eviction_for_any_reason_severe():
    result = flag("eviction", "The landlord may terminate for any reason with 24 hours notice.")
    assert result and result["severity"] == "severe"


def test_self_help_eviction_severe():
    result = flag("eviction", "Upon default, the Landlord may without recourse to court lock the premises and disconnect utilities.")
    assert result and result["severity"] == "severe"


def test_late_fee_per_day_severe():
    result = flag("late_fee", "A late fee of $150 per day applies.")
    assert result and result["severity"] == "severe"


def test_late_fee_words_amount_severe():
    result = flag("late_fee", "Delayed payment shall attract a daily fine of rupees two thousand.")
    assert result and result["severity"] == "severe"


def test_tenant_structural_repairs_severe():
    result = flag("repairs", "The Tenant shall be responsible for all repairs including structural repairs at the Tenant's own expense.")
    assert result and result["severity"] == "severe"


def test_tenant_waives_jury_severe():
    result = flag("waiver", "The Tenant waives the right to a jury trial in any proceeding.")
    assert result and result["severity"] == "severe"


def test_one_sided_arbitration_severe():
    result = flag("arbitration", "All disputes shall be decided by an arbitrator selected solely by the Landlord.")
    assert result and result["severity"] == "severe"


def test_government_contact_ban_severe():
    result = flag("government_contact", "The Tenant shall not approach any government authority with any complaint regarding the premises.")
    assert result and result["severity"] == "severe"


def test_auto_renewal_long_notice_flagged():
    result = flag("renewal", "This lease automatically renews unless the Tenant provides 90 days notice of non-renewal.")
    assert result and result["severity"] in ("moderate", "mild")


# ---- fair clauses must NOT flag (false-positive guards) ----

def test_fair_deposit_not_flagged():
    result = flag("deposit", "The security deposit shall be refundable and returned within 21 days of vacating.")
    assert result is None


def test_landlord_repairs_not_flagged():
    result = flag("repairs", "The Landlord is responsible for structural repairs and maintaining the premises in habitable condition.")
    assert result is None


def test_landlord_shall_not_enter_not_flagged():
    result = flag("entry", "The Landlord shall not enter the premises without prior notice to the Tenant.")
    assert result is None


def test_landlord_waives_fee_not_flagged():
    result = flag("waiver", "The Landlord agrees to waive the late fee for the first instance of delayed payment.")
    assert result is None


def test_no_waiver_boilerplate_not_flagged():
    result = flag("waiver", "No failure by either party to enforce any provision shall constitute a waiver of that provision.")
    assert result is None


def test_no_penalty_not_flagged():
    result = flag("penalty", "No penalty shall apply if the Tenant terminates early after serving notice.")
    assert result is None


def test_mutual_arbitrator_not_flagged():
    result = flag("arbitration", "Any dispute shall be referred to a sole arbitrator appointed mutually by both parties.")
    assert result is None


def test_fair_termination_not_flagged():
    result = flag("eviction", "Either party may terminate this agreement by providing 30 days written notice.")
    assert result is None


def test_late_fee_with_grace_not_flagged():
    result = flag("late_fee", "A late fee of $50 applies if rent is received more than 5 days after the due date, following the grace period.")
    assert result is None


def test_govt_compliance_boilerplate_not_flagged():
    result = flag("government_contact", "The premises comply with all applicable government and municipal authority regulations.")
    assert result is None


# ---- infrastructure ----

def test_classify_dedupes():
    sentences = ["The deposit is non-refundable in full.", "The deposit is non-refundable in full."]
    flags = classify_clauses(sentences, "DEFAULT")
    assert len(flags) == 1


def test_infer_jurisdiction_explicit_wins():
    assert infer_jurisdiction("some california text", "IN-DL") == "IN-DL"


def test_infer_jurisdiction_no_loose_substrings():
    # v1 matched "ca" inside "in case of" -> US-CA. v2 must not.
    assert infer_jurisdiction("in case of emergency call someone") == "DEFAULT"


def test_infer_jurisdiction_full_names():
    assert infer_jurisdiction("the premises at Lajpat Nagar, New Delhi") == "IN-DL"
    assert infer_jurisdiction("located in Los Angeles, California") == "US-CA"
