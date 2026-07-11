import re
import subprocess
import sys
from collections import defaultdict
from datetime import datetime
from functools import lru_cache

import streamlit as st
from pypdf import PdfReader

try:
    import pytesseract
    from pdf2image import convert_from_bytes
except ImportError:  # pragma: no cover - handled gracefully in cloud/runtime
    pytesseract = None
    convert_from_bytes = None

try:
    import spacy
except ImportError:  # pragma: no cover - handled gracefully in cloud/runtime
    spacy = None


JURISDICTION_RULES = {
    "DEFAULT": {
        "entry_notice_required": False,
        "rent_increase_notice_days_min": 30,
        "eviction_notice_days_min": 3,
        "eviction_requires_just_cause": False,
        "deposit_must_be_refundable": True,
        "deposit_max_months": 3,
        "late_fee_threshold": 100,
        "repair_liability_allowed": False,
        "arbitration_neutrality_required": False,
        "renewal_notice_days_min": 30,
        "guest_policy_max_nights": 30,
    },
    "US-CA": {
        "entry_notice_required": True,
        "rent_increase_notice_days_min": 30,
        "eviction_notice_days_min": 3,
        "eviction_requires_just_cause": True,
        "deposit_must_be_refundable": True,
        "deposit_max_months": 3,
        "late_fee_threshold": 100,
        "repair_liability_allowed": False,
        "arbitration_neutrality_required": True,
        "renewal_notice_days_min": 30,
        "guest_policy_max_nights": 30,
        "entry_notice_reference": "CA Civil Code § 1954",
        "eviction_reference": "CA just-cause eviction requirements",
        "deposit_reference": "California deposit rules",
    },
    "US-TX": {
        "entry_notice_required": False,
        "rent_increase_notice_days_min": 30,
        "eviction_notice_days_min": 3,
        "eviction_requires_just_cause": False,
        "deposit_must_be_refundable": True,
        "deposit_max_months": 3,
        "late_fee_threshold": 100,
        "repair_liability_allowed": False,
        "arbitration_neutrality_required": False,
        "renewal_notice_days_min": 30,
        "guest_policy_max_nights": 30,
    },
    "IN-MH": {
        "entry_notice_required": True,
        "rent_increase_notice_days_min": 30,
        "eviction_notice_days_min": 3,
        "eviction_requires_just_cause": False,
        "deposit_must_be_refundable": True,
        "deposit_max_months": 4,
        "late_fee_threshold": 1000,
        "repair_liability_allowed": False,
        "arbitration_neutrality_required": False,
        "renewal_notice_days_min": 30,
        "guest_policy_max_nights": 30,
        "law_reference": "Maharashtra Rent Control Act",
    },
    "IN-DL": {
        "entry_notice_required": True,
        "rent_increase_notice_days_min": 30,
        "eviction_notice_days_min": 1,
        "eviction_requires_just_cause": True,
        "deposit_must_be_refundable": True,
        "deposit_max_months": 6,
        "late_fee_threshold": 1000,
        "repair_liability_allowed": False,
        "arbitration_neutrality_required": True,
        "renewal_notice_days_min": 30,
        "guest_policy_max_nights": 1,
        "entry_notice_reference": "Delhi Rent Control Act notice requirements",
        "eviction_reference": "Delhi Rent Control Act",
        "deposit_reference": "Delhi Rent Control Act deposit rules",
    },
}


@lru_cache(maxsize=1)
def get_nlp():
    if spacy is None:
        return None

    try:
        return spacy.load("en_core_web_sm")
    except OSError:
        try:
            subprocess.check_call([sys.executable, "-m", "spacy", "download", "en_core_web_sm", "-q"])
            return spacy.load("en_core_web_sm")
        except Exception:  # pragma: no cover - fallback for minimal environments
            try:
                return spacy.blank("en")
            except Exception:  # pragma: no cover - fallback for minimal environments
                return None


def set_page_config():
    st.set_page_config(
        page_title="Rent Agreement Analyzer",
        page_icon="📄",
        layout="wide",
    )


def render_header():
    st.title("📄 Rent Agreement Analyzer")
    st.caption(
        "Upload a rent agreement PDF or paste the text to extract key terms, spot risky clauses, and generate a tidy summary."
    )


def extract_pdf_text(uploaded_file):
    text_parts = []
    uploaded_file.seek(0)
    pdf = PdfReader(uploaded_file)

    for page in pdf.pages:
        page_text = page.extract_text() or ""
        if page_text.strip():
            text_parts.append(page_text)

    text = "\n".join(text_parts)
    if text.strip():
        return text

    return extract_text_with_ocr(uploaded_file.getvalue())


def extract_text_with_ocr(pdf_bytes):
    if pytesseract is None or convert_from_bytes is None:
        return ""

    try:
        images = convert_from_bytes(pdf_bytes)
        extracted = []
        for image in images:
            extracted.append(pytesseract.image_to_string(image))
        return "\n".join(extracted)
    except Exception:
        return ""


def normalize_text(text):
    if not text:
        return ""
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{2,}", "\n", text)
    return text.strip()


def detect_language(text):
    if re.search(r"[\u0900-\u097F]", text):
        return "hi"
    return "en"


def translate_text(text, target_language="en"):
    if not text:
        return text

    if target_language not in {"en", "hi"}:
        return text

    if target_language == "en":
        translation_map = {
            "रजिस्टर": "registered",
            "नोटिस": "notice",
            "मासिक": "monthly",
            "किराया": "rent",
            "जमानत": "deposit",
            "मरम्मत": "repair",
            "घुसपैठ": "entry",
            "बाहरी": "outside",
            "बंद": "closed",
            "अधिकार": "rights",
            "अभियोजन": "proceedings",
            "सरकार": "government",
            "समझौता": "agreement",
            "मालिक": "landlord",
            "किरायेदार": "tenant",
            "माह": "month",
            "दिन": "day",
            "अवधि": "term",
            "वापसी": "refund",
            "शुल्क": "fee",
            "दंड": "penalty",
            "वसूली": "recovery",
            "सीमित": "limited",
        }
    else:
        translation_map = {
            "registered": "रजिस्टर",
            "notice": "नोटिस",
            "monthly": "मासिक",
            "rent": "किराया",
            "deposit": "जमानत",
            "repair": "मरम्मत",
            "entry": "घुसपैठ",
            "outside": "बाहरी",
            "closed": "बंद",
            "rights": "अधिकार",
            "proceedings": "अभियोजन",
            "government": "सरकार",
            "agreement": "समझौता",
            "landlord": "मालिक",
            "tenant": "किरायेदार",
            "month": "माह",
            "day": "दिन",
            "term": "अवधि",
            "refund": "वापसी",
            "fee": "शुल्क",
            "penalty": "दंड",
            "recovery": "वसूली",
            "limited": "सीमित",
        }

    def apply_case(word, replacement):
        if not word:
            return replacement
        if word.isupper():
            return replacement.upper()
        if word[0].isupper():
            return replacement.capitalize()
        return replacement

    keys = sorted(translation_map.keys(), key=len, reverse=True)
    pattern = re.compile(r"|".join(re.escape(key) for key in keys))

    def replace_match(match):
        word = match.group(0)
        replacement = translation_map.get(word.lower(), word)
        return apply_case(word, replacement)

    return pattern.sub(replace_match, text)


def preprocess_text(text, target_language="en"):
    normalized = normalize_text(text)
    language = detect_language(normalized)
    if target_language != language:
        normalized = translate_text(normalized, target_language=target_language)
    return normalized, language


def split_sentences(text):
    if not text or not text.strip():
        return []

    nlp = get_nlp()
    if nlp is None:
        return [part.strip() for part in re.split(r"(?<=[.!?])\s+|\n+", text) if part.strip()]

    try:
        doc = nlp(text[:350000])
        sentences = [sentence.text.strip() for sentence in doc.sents if sentence and sentence.text]
    except Exception:
        sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+|\n+", text) if part.strip()]

    return [sentence for sentence in sentences if len(sentence) > 25]


def extract_entities(text):
    nlp = get_nlp()
    if nlp is None:
        return {}

    doc = nlp(text[:350000])
    details = defaultdict(list)

    label_map = {
        "PERSON": "People",
        "ORG": "Organizations",
        "MONEY": "Money",
        "DATE": "Dates",
        "GPE": "Locations",
    }

    for ent in doc.ents:
        bucket = label_map.get(ent.label_)
        if bucket:
            clean = ent.text.strip()
            if clean and len(clean) > 1:
                details[bucket].append(clean)

    for key in list(details.keys()):
        seen = set()
        ordered = []
        for item in details[key]:
            if item.lower() not in seen:
                seen.add(item.lower())
                ordered.append(item)
        details[key] = ordered

    return details


def find_first(patterns, text, flags=re.IGNORECASE):
    for pattern in patterns:
        match = re.search(pattern, text, flags)
        if match:
            value = match.group(1).strip()
            value = re.sub(r"^(?:is|was|are|for|a|an)\s+", "", value, flags=re.IGNORECASE)
            return value
    return "Not clearly found"


def extract_currency(text):
    match = re.search(r"([₹$]\s?[\d,]+(?:\.\d{1,2})?|Rs\.\s?[\d,]+(?:\.\d{1,2})?/?-?)", text)
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
    sentences = split_sentences(normalized)

    rent_match = re.search(r"\bmonthly\s+(?:rent|licence fee|license fee)\b[^$₹\n]{0,40}?((?:Rs\.?|[₹$])\s?[\d,]+(?:\.\d{1,2})?/?-?)", normalized, re.IGNORECASE)
    if not rent_match:
        rent_match = re.search(r"\b(?:rent|licence fee|license fee)\b[^$₹\n]{0,25}?((?:Rs\.?|[₹$])\s?[\d,]+(?:\.\d{1,2})?/?-?)", normalized, re.IGNORECASE)
    rent_value = rent_match.group(1).rstrip(",") if rent_match else "Not clearly found"
    if rent_value.endswith("/-"):
        rent_value = rent_value[:-2] + "/-"
    data["Monthly Rent"] = rent_value

    deposit_match = re.search(r"\bsecurity\s+deposit\b[^$₹\n]{0,40}?((?:Rs\.?|[₹$])\s?[\d,]+(?:\.\d{1,2})?)", normalized, re.IGNORECASE)
    if not deposit_match:
        deposit_match = re.search(r"\b(?:deposit|advance rent)\b[^$₹\n]{0,40}?((?:Rs\.?|[₹$])\s?[\d,]+(?:\.\d{1,2})?)", normalized, re.IGNORECASE)
    deposit_value = deposit_match.group(1).rstrip(",") if deposit_match else "Not clearly found"
    if deposit_value.endswith("/-"):
        deposit_value = deposit_value[:-2] + "/-"
    data["Security Deposit"] = deposit_value

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

    notice_value = "Not clearly found"
    for sentence in sentences:
        lowered = sentence.lower()
        if any(token in lowered for token in ["notice", "vacate", "terminate", "expiry", "renew", "renewal"]):
            day_match = re.search(r"\b(\d+)\s*(day|days)\b", sentence, re.IGNORECASE)
            if day_match:
                amount = int(day_match.group(1))
                label = "day" if amount == 1 else "days"
                notice_value = f"{amount} {label}"
                break
            month_match = re.search(r"\b(\d+)\s*(month|months)\b", sentence, re.IGNORECASE)
            if month_match:
                amount = int(month_match.group(1))
                label = "month" if amount == 1 else "months"
                notice_value = f"{amount} {label}"
                break
    if notice_value == "Not clearly found":
        day_match = re.search(r"\b(\d+)\s*(day|days)\b", normalized, re.IGNORECASE)
        if day_match:
            amount = int(day_match.group(1))
            label = "day" if amount == 1 else "days"
            notice_value = f"{amount} {label}"
        else:
            month_match = re.search(r"\b(\d+)\s*(month|months)\b", normalized, re.IGNORECASE)
            if month_match:
                amount = int(month_match.group(1))
                label = "month" if amount == 1 else "months"
                notice_value = f"{amount} {label}"
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


RISK_RULES = [
    {"term": "automatic renewal", "severity": "Medium", "points": 12, "why": "Can lock a tenant into another term without clear consent."},
    {"term": "non-refundable", "severity": "High", "points": 20, "why": "May limit legitimate recovery of fees or deposits."},
    {"term": "deduct from deposit", "severity": "Medium", "points": 12, "why": "Broad deduction rights may be overused."},
    {"term": "terminate anytime", "severity": "High", "points": 22, "why": "Unbalanced termination language can be risky."},
    {"term": "eviction", "severity": "Medium", "points": 10, "why": "Review the process and legal compliance details."},
    {"term": "late fee", "severity": "Low", "points": 6, "why": "Late fees are common; verify amount and grace period."},
    {"term": "legal action", "severity": "Medium", "points": 10, "why": "Check the dispute process and governing law."},
    {"term": "penalty", "severity": "Medium", "points": 8, "why": "Generic penalties should be clearly bounded."},
    {"term": "cleaning fee", "severity": "Low", "points": 5, "why": "Ensure fee conditions are specific and reasonable."},
]


def detect_red_flags(text, sentences):
    text_lower = text.lower()
    found = []

    for rule in RISK_RULES:
        if rule["term"] in text_lower:
            evidence = ""
            for sentence in sentences:
                if rule["term"] in sentence.lower():
                    evidence = sentence[:220]
                    break
            found.append(
                {
                    "term": rule["term"],
                    "severity": rule["severity"],
                    "points": rule["points"],
                    "why": rule["why"],
                    "evidence": evidence,
                }
            )

    if any("terminate anytime" in item["term"] for item in found):
        found = [item for item in found if item["term"] != "terminate anytime"] + [
            {
                "term": "terminate anytime",
                "severity": "High",
                "points": 22,
                "why": "Unbalanced termination language can be risky.",
                "evidence": "",
            }
        ]

    total_points = sum(item["points"] for item in found)
    score = max(0, 100 - total_points)

    if total_points >= 25 or any(item["severity"] == "High" for item in found):
        band = "High"
    elif total_points >= 12:
        band = "Medium"
    else:
        band = "Low"

    return found, score, band


def extract_important_clauses(sentences):
    keywords = [
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

    scored = []
    for sentence in sentences:
        low = sentence.lower()
        hits = sum(1 for keyword in keywords if keyword in low)
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


def format_list(values, limit=5):
    if not values:
        return "Not clearly found"
    return ", ".join(values[:limit])


def build_risk_flag(category, clause, jurisdiction, rules, law_reference=None):
    severity = "none"
    reason = ""
    lowered = clause.lower()
    if category == "late_fee":
        amount = extract_currency(clause)
        amount_value = extract_number(clause)
        is_excessive = bool(
            amount
            and amount_value is not None
            and ((amount.startswith("$") and amount_value >= rules.get("late_fee_threshold", 100)) or (amount.startswith("₹") and amount_value >= rules.get("late_fee_threshold", 1000)))
        )
        is_per_day = "per day" in lowered or "daily" in lowered
        lacks_grace = "grace period" not in lowered and "grace" not in lowered and ("days" in lowered or "day" in lowered) and "after" in lowered
        if is_excessive or (is_per_day and amount_value is not None and amount_value >= 100):
            severity = "severe"
            reason = "The late fee is unusually high and may be unenforceable."
        elif amount_value is not None and amount_value >= 100 and lacks_grace:
            severity = "moderate"
            reason = "The late fee appears steep and should be tied to a clear grace period and a reasonable cap."
    elif category == "deposit":
        if "non-refundable" in lowered:
            severity = "severe"
            reason = "A non-refundable deposit is risky because deposits should generally be refundable unless the law clearly permits otherwise."
        elif "return" in lowered and re.search(r"\b(\d+)\s*days\b", lowered):
            days = extract_number(clause.lower())
            if days is not None and days < 30:
                severity = "mild"
                reason = "The deposit return window is short and may leave the tenant waiting longer than expected."
        elif "forfeit" in lowered or "forfeits" in lowered:
            severity = "mild"
            reason = "The clause allows forfeiture of a deposit on early exit, which should be reviewed carefully."
    elif category == "rent_increase":
        notice_days = extract_number(clause)
        if notice_days is not None and notice_days < rules.get("rent_increase_notice_days_min", 30):
            severity = "severe"
            reason = "The rent increase notice period is shorter than the minimum generally expected in this jurisdiction."
    elif category == "entry":
        if any(token in lowered for token in ["without notice", "without prior notice", "day or night", "any time", "at any time", "without consent"]):
            severity = "severe"
            reason = "The landlord entry clause is overly broad and may violate notice requirements."
    elif category == "eviction":
        if any(token in lowered for token in ["for any reason", "48 hours", "24 hours", "24hrs", "immediately", "instant", "without cause"]):
            severity = "severe"
            reason = "The eviction clause is unusually short and may fail to meet the required notice or just-cause standards."
        elif "terminate" in lowered or "vacate" in lowered:
            severity = "moderate"
            reason = "The termination language should be checked for fairness and legal compliance."
    elif category == "waiver":
        severity = "severe"
        reason = "The clause waives important tenant rights and may be unenforceable."
    elif category == "arbitration":
        severity = "severe"
        reason = "The dispute clause appears one-sided because it restricts access to neutral adjudication."
    elif category == "penalty":
        severity = "severe"
        reason = "The penalty is excessive and may be treated as an unenforceable punitive charge."
    elif category == "renewal":
        notice_days = extract_number(clause)
        if notice_days is not None and notice_days > rules.get("renewal_notice_days_min", 30):
            severity = "moderate"
            reason = "The renewal notice period is more burdensome than typical and should be reviewed."
        elif "automatically renew" in lowered or "renew for" in lowered or "auto renew" in lowered:
            severity = "moderate"
            reason = "The renewal clause may lock the tenant into another term without a clear chance to opt out."
    elif category == "repairs":
        if any(token in lowered for token in ["structural", "roof", "all repairs", "major repairs", "habitability", "damage"]):
            severity = "severe"
            reason = "The clause shifts structural repair obligations to the tenant in a way that is typically improper."
    elif category == "guest_policy":
        severity = "moderate"
        reason = "The guest policy is unusually restrictive and may be difficult to enforce fairly."
    elif category == "government_contact":
        severity = "severe"
        reason = "The clause punishes lawful contact with government authorities and is likely unenforceable."
    elif category == "indemnity":
        if any(token in lowered for token in ["indemnify", "hold harmless", "all claims", "all liabilities", "all damages"]):
            severity = "severe"
            reason = "The indemnity clause could expose the tenant to broad liability beyond the lease’s ordinary scope."
    elif category == "subletting":
        severity = "moderate"
        reason = "The subletting clause may be too restrictive and should be clarified."

    if severity != "none":
        return {
            "category": category,
            "clause": clause,
            "severity": severity,
            "reason": reason,
            "law_reference": law_reference or rules.get("entry_notice_reference") or rules.get("eviction_reference") or rules.get("deposit_reference") or "Applicable local tenancy law",
        }
    return None


def classify_clauses(sentences, jurisdiction):
    rules = JURISDICTION_RULES.get(jurisdiction, JURISDICTION_RULES["DEFAULT"])
    flags = []
    for sentence in sentences:
        text = sentence.lower()
        if any(token in text for token in ["late fee", "late fees", "delay charge", "penalty fee"]):
            risk = build_risk_flag("late_fee", sentence, jurisdiction, rules, "Applicable late-fee law")
            if risk:
                flags.append(risk)
        if any(token in text for token in ["deposit", "security deposit", "advance rent", "refundable deposit"]):
            risk = build_risk_flag("deposit", sentence, jurisdiction, rules, rules.get("deposit_reference"))
            if risk:
                flags.append(risk)
        if any(token in text for token in ["rent increase", "increase in rent", "increase of rent", "increased rent", "rent may be increased", "increase", "increased"]) and ("rent" in text or "notice" in text):
            risk = build_risk_flag("rent_increase", sentence, jurisdiction, rules)
            if risk:
                flags.append(risk)
        if any(token in text for token in ["entry", "enter", "access", "premises", "without notice", "without prior notice", "day or night", "at any time"]):
            risk = build_risk_flag("entry", sentence, jurisdiction, rules, rules.get("entry_notice_reference"))
            if risk:
                flags.append(risk)
        if any(token in text for token in ["evict", "eviction", "vacate", "forfeited", "forfeit", "immediately", "without cause", "for any reason", "terminate anytime", "terminate at any time", "24 hours", "48 hours"]):
            risk = build_risk_flag("eviction", sentence, jurisdiction, rules, rules.get("eviction_reference"))
            if risk:
                flags.append(risk)
        if any(token in text for token in ["waive", "waiver", "waives", "right to challenge", "right to approach any court"]):
            risk = build_risk_flag("waiver", sentence, jurisdiction, rules)
            if risk:
                flags.append(risk)
        if any(token in text for token in ["arbitrator", "arbitration", "jury trial", "neutral adjudication"]):
            risk = build_risk_flag("arbitration", sentence, jurisdiction, rules)
            if risk:
                flags.append(risk)
        if any(token in text for token in ["penalty", "fine", "per nail", "per hole", "charge per"]):
            risk = build_risk_flag("penalty", sentence, jurisdiction, rules)
            if risk:
                flags.append(risk)
        if any(token in text for token in ["renew", "renewal", "automatically renew", "auto renew"]):
            risk = build_risk_flag("renewal", sentence, jurisdiction, rules)
            if risk:
                flags.append(risk)
        if any(token in text for token in ["repair", "structural", "roof", "habitability", "maintenance", "damage"]):
            risk = build_risk_flag("repairs", sentence, jurisdiction, rules)
            if risk:
                flags.append(risk)
        if any(token in text for token in ["guest", "visitor", "stay"]):
            risk = build_risk_flag("guest_policy", sentence, jurisdiction, rules)
            if risk:
                flags.append(risk)
        if any(token in text for token in ["government", "authority", "police", "legal authority"]):
            risk = build_risk_flag("government_contact", sentence, jurisdiction, rules)
            if risk:
                flags.append(risk)
        if any(token in text for token in ["indemnify", "indemnity", "hold harmless", "all claims", "all liabilities"]):
            risk = build_risk_flag("indemnity", sentence, jurisdiction, rules)
            if risk:
                flags.append(risk)
        if any(token in text for token in ["sublet", "subletting", "assign", "transfer"]):
            risk = build_risk_flag("subletting", sentence, jurisdiction, rules)
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


def infer_jurisdiction(text, jurisdiction=None):
    if jurisdiction:
        return jurisdiction
    lowered = text.lower()
    if any(token in lowered for token in ["california", "ca", "los angeles"]):
        return "US-CA"
    if any(token in lowered for token in ["texas", "austin", "tx"]):
        return "US-TX"
    if any(token in lowered for token in ["maharashtra", "mumbai", "mh"]):
        return "IN-MH"
    if any(token in lowered for token in ["delhi", "dl"]):
        return "IN-DL"
    return "DEFAULT"


def analyze_agreement(text, jurisdiction=None, target_language="en"):
    processed_text, _ = preprocess_text(text, target_language=target_language)
    sentences = split_sentences(processed_text)
    jurisdiction_code = infer_jurisdiction(processed_text, jurisdiction)
    rules = JURISDICTION_RULES.get(jurisdiction_code, JURISDICTION_RULES["DEFAULT"])
    entities = extract_entities(processed_text)
    key_terms = extract_key_terms(processed_text)
    risk_flags = classify_clauses(sentences, jurisdiction_code)
    score = 100
    severity_counts = {"none": 0, "mild": 0, "moderate": 0, "severe": 0}
    for flag in risk_flags:
        severity_counts[flag["severity"]] += 1
        score -= {"mild": 8, "moderate": 16, "severe": 24}.get(flag["severity"], 0)
    score = max(0, score)
    if severity_counts["severe"]:
        band = "High"
    elif severity_counts["moderate"] or severity_counts["mild"] >= 2:
        band = "Medium"
    else:
        band = "Low"

    if risk_flags:
        if any(flag["severity"] == "severe" for flag in risk_flags):
            summary = (
                "This lease contains several clauses that appear one-sided or potentially unlawful. "
                "The strongest concerns are around fees, notice rights, eviction, and repair obligations, and those terms should be revised before signing."
            )
        elif any(flag["severity"] == "moderate" for flag in risk_flags):
            summary = (
                "This lease has a few advisory concerns that should be reviewed before signing. "
                "The main issues are around notice periods, deposit handling, or dispute rights, but they are not as severe as the most problematic leases."
            )
        else:
            summary = (
                "This lease has a few mild concerns that are worth reviewing. "
                "They appear more advisory than unlawful, but the terms should still be clarified to avoid later disputes."
            )
    else:
        summary = (
            "This lease appears broadly fair and tenant-friendly. "
            "The core terms around rent, deposit, notice, and fees look balanced and do not show obvious illegal or unusually one-sided clauses."
        )

    recommendation = ""
    if risk_flags:
        recommendation = "Revise the risky clauses before signing and ask for a local tenancy-law review."
    else:
        recommendation = "The draft looks broadly balanced; keep the document in plain language and preserve clear notice and repair obligations."

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
        "risk_flags": risk_flags,
        "summary": summary,
        "score": score,
        "band": band,
        "entities": entities,
        "recommendation": recommendation,
    }


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
            evidence = risk.get("evidence") or ""
            lines.append(f"- [{risk['severity']}] {str(label).title()} | Why: {reason}")
            if evidence:
                lines.append(f"  Evidence: {evidence}")
    else:
        lines.append("- No major suspicious terms from the configured risk list.")
    lines.append("")
    lines.append("6) DISCLAIMER")
    lines.append("- This is an automated document review, not legal advice.")
    lines.append("- Validate key clauses with the signed agreement and local tenancy laws.")

    return "\n".join(lines)


def render_sidebar():
    with st.sidebar:
        st.header("How to use")
        st.write("1. Upload a PDF or paste the agreement text.")
        st.write("2. Click Analyze Agreement.")
        st.write("3. Review the summary, key terms, and risk notes.")

        st.divider()
        st.caption("Tip: text-based PDFs work best. Scanned image PDFs may not extract reliably.")


def main():
    set_page_config()
    render_header()
    render_sidebar()

    st.markdown(
        """
        <style>
        .stApp { background: linear-gradient(135deg, #f5fbff 0%, #f8fff9 100%); }
        .block-container { padding-top: 1.5rem; }
        .stTabs [data-baseweb="tab-list"] { gap: 0.5rem; }
        .stTabs [data-baseweb="tab"] { border-radius: 999px; padding: 0.4rem 0.8rem; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    uploaded_file = st.file_uploader("Upload a rent agreement PDF", type=["pdf"])
    pasted_text = st.text_area(
        "Or paste the agreement text directly",
        height=220,
        placeholder="Paste the agreement text here if you do not want to upload a PDF.",
    )

    st.subheader("Translation options")
    target_language = st.selectbox("Translate detected agreement text", ["en", "hi"], format_func=lambda value: "English" if value == "en" else "Hindi")
    show_translation = st.checkbox("Show translated preview", value=True)

    if st.button("Analyze Agreement"):
        if uploaded_file is not None:
            raw_text = extract_pdf_text(uploaded_file)
        else:
            raw_text = pasted_text

        text = normalize_text(raw_text or "")
        if not text:
            st.error("Please upload a PDF or paste some agreement text before analyzing.")
            st.stop()

        with st.spinner("Analyzing agreement..."):
            analysis = analyze_agreement(text, target_language="en")
            translated_text = translate_text(text, target_language=target_language)
            sentences = split_sentences(text)
            entities = extract_entities(text)
            key_terms = extract_key_terms(text)
            clauses = extract_important_clauses(sentences)
            risks = analysis.get("risk_flags", [])
            score = analysis.get("score", 100)
            band = analysis.get("band", "Low")
            summary = generate_summary(text, entities, key_terms, clauses, risks, score, band)
            summary = summary + f"\n\nRecommendation: {analysis.get('recommendation', '')}"

        if show_translation and translated_text:
            st.info(f"Translated preview ({'English' if target_language == 'en' else 'Hindi'}):")
            st.write(translated_text)
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Words reviewed", len(text.split()))
        with col2:
            st.metric("Sentence count", len(sentences))
        with col3:
            st.metric("Source", uploaded_file.name if uploaded_file is not None else "Pasted text")

        if band == "Low":
            risk_cls = "risk-low"
        elif band == "Medium":
            risk_cls = "risk-medium"
        else:
            risk_cls = "risk-high"

        st.markdown(
            f"<div style='padding: 1rem; border-radius: 12px; border: 1px solid #dce7ef; background: white; margin-bottom: 1rem;'>"
            f"<h3 style='margin-bottom: 0.2rem;'>Overall Risk</h3>"
            f"<p style='font-size: 2rem; font-weight: 700; margin: 0;'>{score}/100</p>"
            f"<p class='{risk_cls}' style='font-weight: 700; margin-top: 0.25rem;'>{band} Risk</p></div>",
            unsafe_allow_html=True,
        )

        tab1, tab2, tab3, tab4 = st.tabs(["Summary", "Key Terms", "Risks", "Full Text"])

        with tab1:
            st.code(summary, language="markdown")
            st.download_button(
                "Download summary",
                data=summary,
                file_name="rent_agreement_summary.txt",
                mime="text/plain",
            )

        with tab2:
            st.json(key_terms)
            st.subheader("Named entities")
            for category, values in entities.items():
                if values:
                    st.write(f"**{category}**: {', '.join(values[:12])}")

            st.subheader("Important clauses")
            for clause in clauses:
                st.write(f"- {clause}")

        with tab3:
            if risks:
                for risk in risks:
                    st.warning(f"[{risk['severity']}] {risk['category'].title()} - {risk['reason']}")
                    if risk.get("law_reference"):
                        st.caption(f"Reference: {risk['law_reference']}")
            else:
                st.success("No suspicious terms were detected from the configured risk list.")

        with tab4:
            with st.expander("View full agreement text", expanded=False):
                st.text(text)


if __name__ == "__main__":
    main()
