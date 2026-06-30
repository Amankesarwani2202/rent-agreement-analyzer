import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_PATH = ROOT / "app.py"

spec = importlib.util.spec_from_file_location("rent_agreement_analyzer_app", APP_PATH)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


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


def test_extract_text_with_ocr_returns_empty_when_unavailable(monkeypatch):
    monkeypatch.setattr(module, "pytesseract", None, raising=False)
    monkeypatch.setattr(module, "pdf2image", None, raising=False)

    assert module.extract_text_with_ocr(b"fake-pdf") == ""
