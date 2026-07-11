import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_PATH = ROOT / "app.py"

spec = importlib.util.spec_from_file_location("rent_agreement_analyzer_app", APP_PATH)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


LEASE_FIXTURES = {
    "lease1": {
        "jurisdiction": "US-TX",
        "text": """
        This residential lease is between Landlord and Tenant. Monthly rent is $1,850 per month.
        A late fee of $50 will apply after a 5-day grace period. The security deposit is $1,850 and is refundable.
        The deposit must be returned within 30 days after move-out. The term is 1 year. The tenant must give 30 days' notice to terminate.
        """,
    },
    "lease2": {
        "jurisdiction": "US-CA",
        "text": """
        Late fees are $200 per day. The security deposit is non-refundable and equals $7,200, three months' rent.
        Rent may be increased with only 3 days' notice. The landlord may enter the premises without notice.
        The landlord may issue a 24-hour eviction notice for any reason. Tenant waives all liability and waives the right to challenge the lease.
        Any dispute must be decided by a landlord-chosen arbitrator and jury trial is waived. Tenant shall pay $1,000 per nail hole.
        The lease renews automatically and the tenant must provide 90-day certified-mail renewal notice to avoid renewal.
        Tenant is responsible for structural and roof repairs.
        """,
    },
    "lease3": {
        "jurisdiction": "IN-MH",
        "text": """
        This leave and licence agreement is governed by the Maharashtra Rent Control Act. Monthly rent is ₹28,000.
        The lease term is 11 months. The refundable deposit is ₹1,12,000, four months' rent.
        The lessee must give one month notice to exit. The deposit shall be returned within 15 days after exit.
        If the tenant exits early, the tenant forfeits two months' deposit. Stamp duty shall be shared equally 50/50 by both parties.
        """,
    },
    "lease4": {
        "jurisdiction": "IN-DL",
        "text": """
        Monthly Rent & Fees: ₹1,000 per day late fee; payment must be made in cash only and no receipt is issued.
        Security Deposit: 6-month non-refundable deposit of ₹2,10,000.
        Repairs: tenant is responsible for all structural repairs and roof damage.
        Entry: landlord may enter day or night without prior notice.
        Eviction: landlord may evict the tenant within 48 hours and demand vacation in 24 hours.
        Waiver: tenant waives the right to approach any court.
        Guest Policy: guests may stay only one night, and any extra night costs ₹5,000.
        Arbitration: disputes will be resolved only by a landlord-appointed arbitrator and no tribunal access.
        Renewal: notice to renew must be sent by registered mail at least 120 days before expiry.
        Government Contact: contacting any government authority is ground for eviction.
        """,
    },
}


def test_extract_key_terms_finds_common_values():
    text = """
    Monthly rent is $1,500.
    Security deposit is $3,000.
    The lease term is 12 months.
    The notice period is 30 days.
    Rent is due on the first of each month.
    Utilities are included.
    No pets allowed.
    """

    terms = module.extract_key_terms(text)

    assert terms["Monthly Rent"] == "$1,500"
    assert terms["Security Deposit"] == "$3,000"
    assert terms["Lease Term"] == "12 months"
    assert terms["Notice Period"] == "30 days"


def test_detect_red_flags_returns_high_risk_for_termination_language():
    text = "The landlord may terminate anytime and deduct from deposit for any reason."
    sentences = [text]

    risks, score, band = module.detect_red_flags(text, sentences)

    assert any(r["term"] == "terminate anytime" for r in risks)
    assert band == "High"
    assert score <= 100


def test_split_sentences_falls_back_when_spacy_sentence_splitting_fails(monkeypatch):
    class FakeDoc:
        def __init__(self, text):
            self.text = text

        @property
        def sents(self):
            raise ValueError("sentence segmentation unavailable")

    class FakeNLP:
        def __call__(self, text):
            return FakeDoc(text)

    monkeypatch.setattr(module, "get_nlp", lambda: FakeNLP())

    text = (
        "This is sentence one that is long enough. "
        "This is sentence two that is long enough. "
        "This is sentence three that is long enough."
    )
    sentences = module.split_sentences(text)

    assert sentences == [
        "This is sentence one that is long enough.",
        "This is sentence two that is long enough.",
        "This is sentence three that is long enough.",
    ]


def test_extract_text_with_ocr_returns_empty_when_unavailable(monkeypatch):
    monkeypatch.setattr(module, "pytesseract", None, raising=False)
    monkeypatch.setattr(module, "pdf2image", None, raising=False)

    assert module.extract_text_with_ocr(b"fake-pdf") == ""


def test_extract_key_terms_handles_the_austin_sample_lease():
    text = """
    RESIDENTIAL LEASE AGREEMENT
    Standard Tenancy — 123 Maple Street, Austin, TX 78701
    Lease Start: August 1, 2025 Lease End: July 31, 2026
    1. RENT
    Monthly rent is $1,850, due on the 1st of each month. A grace period of 5 days applies.
    2. SECURITY DEPOSIT
    A security deposit of $1,850 (one month's rent) is due upon signing.
    8. TERMINATION & NOTICE
    Either party must provide 30 days' written notice to terminate at lease end.
    """

    terms = module.extract_key_terms(text)

    assert terms["Monthly Rent"] == "$1,850"
    assert terms["Security Deposit"] == "$1,850"
    assert "year" in terms["Lease Term"].lower()
    assert terms["Notice Period"] == "30 days"
    assert "1st" in terms["Payment Due"].lower()


def test_analyze_agreement_handles_mumbai_leave_and_licence_sample():
    text = """
    LEAVE AND LICENCE AGREEMENT Mumbai, Maharashtra, India
    Term: 1st October 2025 to 31st August 2026 (11 months)
    The monthly licence fee is Rs. 22,000/-, payable by the 5th of each month.
    The Licensee has paid Rs. 66,000/- as advance rent.
    The Licensor may enter the premises at any time without prior notice for the remainder of the term.
    Unless the Licensee provides written notice of intent to vacate no less than ninety (90) days before expiry, the agreement automatically renews for eleven (11) months.
    """

    analysis = module.analyze_agreement(text, jurisdiction="IN-MH")

    assert analysis["jurisdiction"] == "IN-MH"
    assert analysis["key_terms"]["rent"] == "Rs. 22,000/-"
    assert analysis["key_terms"]["lease_term"] == "11 months"
    assert analysis["key_terms"]["notice_period"] == "90 days"
    assert any(flag["category"] == "entry" for flag in analysis["risk_flags"])
    assert any(flag["category"] == "renewal" for flag in analysis["risk_flags"])


def test_analyze_agreement_handles_leases_across_jurisdictions():
    lease1 = module.analyze_agreement(LEASE_FIXTURES["lease1"]["text"], jurisdiction="US-TX")
    assert lease1["jurisdiction"] == "US-TX"
    assert lease1["risk_flags"] == []
    assert "fair" in lease1["summary"].lower() or "tenant-friendly" in lease1["summary"].lower()

    lease2 = module.analyze_agreement(LEASE_FIXTURES["lease2"]["text"], jurisdiction="US-CA")
    assert lease2["jurisdiction"] == "US-CA"
    assert len(lease2["risk_flags"]) >= 10
    categories = {flag["category"] for flag in lease2["risk_flags"]}
    assert {"late_fee", "deposit", "rent_increase", "entry", "eviction", "waiver", "arbitration", "penalty", "renewal", "repairs"}.issubset(categories)
    assert any(flag["severity"] == "severe" for flag in lease2["risk_flags"])

    lease3 = module.analyze_agreement(LEASE_FIXTURES["lease3"]["text"], jurisdiction="IN-MH")
    assert lease3["jurisdiction"] == "IN-MH"
    assert lease3["risk_flags"]
    assert all(flag["severity"] in {"mild", "moderate"} for flag in lease3["risk_flags"])
    assert not any(flag["severity"] == "severe" for flag in lease3["risk_flags"])

    lease4 = module.analyze_agreement(LEASE_FIXTURES["lease4"]["text"], jurisdiction="IN-DL")
    assert lease4["jurisdiction"] == "IN-DL"
    assert len(lease4["risk_flags"]) >= 10
    categories = {flag["category"] for flag in lease4["risk_flags"]}
    assert {"late_fee", "deposit", "repairs", "entry", "eviction", "waiver", "guest_policy", "arbitration", "renewal", "government_contact"}.issubset(categories)


def test_translate_text_supports_hindi_and_english_round_trip():
    english = module.translate_text("किराया और जमानत", target_language="en")
    assert "rent" in english.lower()
    assert "deposit" in english.lower()

    hindi = module.translate_text("rent deposit notice", target_language="hi")
    assert "किराया" in hindi
    assert "जमानत" in hindi
    assert "नोटिस" in hindi


def test_analyze_agreement_detects_indemnity_and_repair_risks():
    text = "The tenant must indemnify the landlord for all claims and repair all structural damage."
    analysis = module.analyze_agreement(text, jurisdiction="IN-DL")

    categories = {flag["category"] for flag in analysis["risk_flags"]}
    assert "indemnity" in categories
    assert "repairs" in categories
