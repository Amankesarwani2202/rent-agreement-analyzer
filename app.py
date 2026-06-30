import re
import subprocess
import sys
from collections import defaultdict
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
    st.info("This version is optimized for Streamlit Cloud and supports both native text PDFs and scanned-image PDFs when OCR is available.")


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
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{2,}", "\n", text)
    return text.strip()


def split_sentences(text):
    nlp = get_nlp()
    if nlp is None:
        return [part.strip() for part in re.split(r"(?<=[.!?])\s+", text) if part.strip()]

    doc = nlp(text[:350000])
    return [sentence.text.strip() for sentence in doc.sents if len(sentence.text.strip()) > 30]


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


def extract_key_terms(text):
    data = {}

    data["Monthly Rent"] = find_first(
        [
            r"(?:monthly\s+rent|rent\s+shall\s+be|rent\s+is)\s*[:\-]?\s*(\$?\s?[\d,]+(?:\.\d{1,2})?)",
            r"rent\s*[:\-]?\s*(\$?\s?[\d,]+(?:\.\d{1,2})?)",
        ],
        text,
    )

    data["Security Deposit"] = find_first(
        [
            r"(?:security\s+deposit|deposit\s+amount)\s*(?:is|was|are|amount)?\s*[:\-]?\s*(\$?\s?[\d,]+(?:\.\d{1,2})?)",
            r"deposit\s*(?:is|was|are|amount)?\s*[:\-]?\s*(\$?\s?[\d,]+(?:\.\d{1,2})?)",
        ],
        text,
    )

    data["Lease Term"] = find_first(
        [
            r"(?:lease\s+term|term\s+of\s+this\s+agreement)\s*[:\-]?\s*([^\.\n]{12,120})",
            r"for\s+a\s+term\s+of\s+([^\.\n]{8,120})",
        ],
        text,
    )

    data["Notice Period"] = find_first(
        [
            r"(?:notice\s+period|written\s+notice)\s*[:\-]?\s*([^\.\n]{6,90})",
            r"(?:give|providing)\s+([^\.\n]{4,60}\s+notice)",
        ],
        text,
    )

    data["Payment Due"] = find_first(
        [
            r"(?:rent\s+due|due\s+date|payable\s+on)\s*[:\-]?\s*([^\.\n]{4,80})",
            r"on\s+or\s+before\s+the\s+([^\.\n]{4,40})",
        ],
        text,
    )

    data["Utilities"] = find_first(
        [
            r"utilities\s*[:\-]?\s*([^\.\n]{8,140})",
            r"tenant\s+shall\s+pay\s+for\s+([^\.\n]{8,120})",
        ],
        text,
    )

    data["Pet Policy"] = find_first(
        [
            r"pet(?:s)?\s*(?:policy)?\s*[:\-]?\s*([^\.\n]{6,120})",
            r"no\s+pets\s+([^\.\n]{0,90})",
        ],
        text,
    )

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
            lines.append(f"- [{risk['severity']}] {risk['term'].title()} | Why: {risk['why']}")
            if risk["evidence"]:
                lines.append(f"  Evidence: {risk['evidence']}")
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
            sentences = split_sentences(text)
            entities = extract_entities(text)
            key_terms = extract_key_terms(text)
            clauses = extract_important_clauses(sentences)
            risks, score, band = detect_red_flags(text, sentences)
            summary = generate_summary(text, entities, key_terms, clauses, risks, score, band)

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
                    st.warning(f"[{risk['severity']}] {risk['term'].title()} - {risk['why']}")
                    if risk["evidence"]:
                        st.caption(f"Evidence: {risk['evidence']}")
            else:
                st.success("No suspicious terms were detected from the configured risk list.")

        with tab4:
            with st.expander("View full agreement text", expanded=False):
                st.text(text)


if __name__ == "__main__":
    main()
