"""Key-term and clause extraction (regex-based; replaced by typed
normalizers in Phase 1 - see ROBUSTNESS_PLAN.md section 3.1)."""

import re
from datetime import datetime

from rent_analyzer.preprocess import normalize_text, split_sentences


def find_first(patterns, text, flags=re.IGNORECASE):
    for pattern in patterns:
        match = re.search(pattern, text, flags)
        if match:
            value = match.group(1).strip()
            value = re.sub(r"^(?:is|was|are|for|a|an)\s+", "", value, flags=re.IGNORECASE)
            return value
    return "Not clearly found"


def extract_currency(text):
    match = re.search(r"([₹$]\s?[\d,]+(?:\.\d{1,2})?)", text)
    if match:
        return match.group(1)
    return None


def extract_number(text):
    match = re.search(r"(\d+(?:,\d{3})*(?:\.\d{1,2})?|\d+)", text)
    if match:
        return float(match.group(1).replace(",", "")) if "." in match.group(1) else int(match.group(1).replace(",", ""))
    return None


def extract_key_terms(text):
    data = {}
    normalized = normalize_text(text)

    rent_match = re.search(r"\bmonthly\s+rent\b[^$₹\n]{0,40}?([₹$]\s?[\d,]+(?:\.\d{1,2})?)", normalized, re.IGNORECASE)
    if not rent_match:
        rent_match = re.search(r"\brent\b[^$₹\n]{0,25}?([₹$]\s?[\d,]+(?:\.\d{1,2})?)", normalized, re.IGNORECASE)
    data["Monthly Rent"] = rent_match.group(1).rstrip(",") if rent_match else "Not clearly found"

    deposit_match = re.search(r"\bsecurity\s+deposit\b[^$₹\n]{0,40}?([₹$]\s?[\d,]+(?:\.\d{1,2})?)", normalized, re.IGNORECASE)
    if not deposit_match:
        deposit_match = re.search(r"\bdeposit\b[^$₹\n]{0,40}?([₹$]\s?[\d,]+(?:\.\d{1,2})?)", normalized, re.IGNORECASE)
    data["Security Deposit"] = deposit_match.group(1).rstrip(",") if deposit_match else "Not clearly found"

    lease_term = "Not clearly found"
    start_match = re.search(r"lease\s+start[:\s]+([A-Za-z]+\s+\d{1,2},\s*\d{4})", normalized, re.IGNORECASE)
    end_match = re.search(r"lease\s+end[:\s]+([A-Za-z]+\s+\d{1,2},\s*\d{4})", normalized, re.IGNORECASE)
    if start_match and end_match:
        try:
            start_date = datetime.strptime(start_match.group(1), "%B %d, %Y")
            end_date = datetime.strptime(end_match.group(1), "%B %d, %Y")
            delta_years = (end_date.year - start_date.year)
            if delta_years >= 1:
                lease_term = f"{delta_years} year" if delta_years == 1 else f"{delta_years} years"
            else:
                lease_term = f"{(end_date.year - start_date.year) * 12} months"
        except ValueError:
            lease_term = "Not clearly found"
    if lease_term == "Not clearly found":
        term_match = re.search(r"\b(\d+)\s*(?:month|months|year|years)\b", normalized, re.IGNORECASE)
        if term_match:
            lease_term = term_match.group(0)
    data["Lease Term"] = lease_term

    notice_match = re.search(r"\b(\d+)\s*(?:day|days|month|months)\b[^\.\n]{0,40}\bnotice\b", normalized, re.IGNORECASE)
    if notice_match:
        notice_value = notice_match.group(0)
    else:
        notice_match = re.search(r"\bnotice\s+period\b[^\.\n]{0,20}\b(\d+)\s*(?:day|days|month|months)\b", normalized, re.IGNORECASE)
        if notice_match:
            notice_value = notice_match.group(0)
        else:
            notice_match = re.search(r"\b(\d+)\s*(?:day|days|month|months)\b", normalized, re.IGNORECASE)
            notice_value = notice_match.group(0) if notice_match else "Not clearly found"
    notice_value = re.sub(r"\s+written\s+notice", "", notice_value, flags=re.IGNORECASE).strip()
    duration_match = re.search(r"(\d+)\s*(day|days|month|months)", notice_value, re.IGNORECASE)
    if duration_match:
        amount = int(duration_match.group(1))
        unit = duration_match.group(2).lower()
        if unit.startswith("day"):
            label = "day" if amount == 1 else "days"
        else:
            label = "month" if amount == 1 else "months"
        data["Notice Period"] = f"{amount} {label}"
    else:
        data["Notice Period"] = notice_value

    payment_due = "Not clearly found"
    due_match = re.search(r"\bdue\s+on\s+the\s+([0-9]+(?:st|nd|rd|th))", normalized, re.IGNORECASE)
    if due_match:
        payment_due = f"Due on the {due_match.group(1)}"
    data["Payment Due"] = payment_due

    utility_match = re.search(r"utilities\s*[:\-]?\s*([^\.\n]{8,140})", normalized, re.IGNORECASE)
    data["Utilities"] = utility_match.group(1).strip() if utility_match else "Not clearly found"

    pet_match = re.search(r"pet(?:s)?\s*(?:policy)?\s*[:\-]?\s*([^\.\n]{6,140})", normalized, re.IGNORECASE)
    data["Pet Policy"] = pet_match.group(1).strip() if pet_match else "Not clearly found"

    return data


CLAUSE_KEYWORDS = [
    "rent",
    "deposit",
    "notice",
    "late fee",
    "termination",
    "utilities",
    "pets",
    "maintenance",
    "repair",
    "security",
    "payment",
    "sublet",
    "renewal",
    "inspection",
    "damage",
]


def extract_important_clauses(sentences):
    scored = []
    for sentence in sentences:
        low = sentence.lower()
        hits = sum(1 for keyword in CLAUSE_KEYWORDS if keyword in low)
        if hits > 0:
            scored.append((hits, len(sentence), sentence))

    scored.sort(key=lambda item: (item[0], -abs(170 - item[1])), reverse=True)

    unique = []
    seen = set()
    for _, _, clause in scored:
        key = clause.lower()
        if key not in seen:
            seen.add(key)
            unique.append(clause)
        if len(unique) >= 8:
            break

    return unique
