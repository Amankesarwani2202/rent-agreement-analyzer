from rent_analyzer.facts import extract_currency, extract_key_terms, extract_number


def test_extract_currency_dollar():
    assert extract_currency("late fee of $150 per day") == "$150"


def test_extract_currency_rupee():
    assert extract_currency("rent of ₹25,000 per month") == "₹25,000"


def test_extract_currency_none():
    assert extract_currency("no money mentioned here") is None


def test_extract_number_grouped():
    assert extract_number("deposit of 2,50,000") == 2


def test_extract_number_plain():
    assert extract_number("within 21 days") == 21


def test_key_terms_rent_and_deposit():
    text = "The monthly rent is $2,400. The Tenant shall pay a security deposit of $2,400."
    terms = extract_key_terms(text)
    assert terms["Monthly Rent"] == "$2,400"
    assert terms["Security Deposit"] == "$2,400"


def test_key_terms_notice_period():
    text = "Either party may terminate by providing 30 days written notice."
    terms = extract_key_terms(text)
    assert terms["Notice Period"] == "30 days"


def test_key_terms_missing():
    terms = extract_key_terms("This document mentions nothing relevant at all!")
    assert terms["Monthly Rent"] == "Not clearly found"
    assert terms["Security Deposit"] == "Not clearly found"
