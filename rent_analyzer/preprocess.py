"""Text normalization, language detection, sentence splitting, entities."""

import re
import subprocess
import sys
from collections import defaultdict
from functools import lru_cache

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


def normalize_text(text):
    if not text:
        return ""
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{2,}", "\n", text)
    return text.strip()


def preprocess_text(text):
    """Normalize, and if the agreement is in an Indian language, convert it
    to analyzable English via the offline glossary translator."""
    from rent_analyzer.translate import to_english_for_analysis

    normalized = normalize_text(text)
    english, language = to_english_for_analysis(normalized)
    return english, language


# Don't split after common abbreviations (Rs. 30,000 must stay one sentence).
_SENT_SPLIT = re.compile(
    r"(?<=[.!?])(?<!\bRs\.)(?<!\bNo\.)(?<!\bMr\.)(?<!\bDr\.)(?<!\bMrs\.)(?<!\bSt\.)(?<!\bvs\.)\s+|\n+"
)


def _regex_sentences(text):
    return [part.strip() for part in _SENT_SPLIT.split(text) if part and part.strip()]


def split_sentences(text):
    if not text or not text.strip():
        return []

    nlp = get_nlp()
    if nlp is None:
        return [s for s in _regex_sentences(text) if len(s) > 15]

    try:
        doc = nlp(text[:350000])
        sentences = [sentence.text.strip() for sentence in doc.sents if sentence and sentence.text]
    except Exception:
        sentences = _regex_sentences(text)

    return [sentence for sentence in sentences if len(sentence) > 15]


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

    return dict(details)
