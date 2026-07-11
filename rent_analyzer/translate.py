"""Offline translation between English and the top-5 Indian languages:
Hindi, Bengali, Marathi, Telugu, Tamil - any direction, pivoting via English.

No external API. Two engines:

1. LEXICON (always available, pure code): a curated legal/rental-domain
   glossary. Phrase-first longest-match substitution. Numbers, currency,
   names and unknown words pass through untouched. Great for legal terms
   and gist; it is NOT general-purpose sentence translation.

2. NEURAL (optional): if the user has installed `argostranslate` plus its
   language packages (currently exists for en<->hi and en<->bn), those pairs
   are translated by a local neural model - still fully offline. See
   tools/setup_neural.py.
"""

import re
from functools import lru_cache

LANGUAGES = {
    "en": "English",
    "hi": "Hindi (हिन्दी)",
    "bn": "Bengali (বাংলা)",
    "mr": "Marathi (मराठी)",
    "te": "Telugu (తెలుగు)",
    "ta": "Tamil (தமிழ்)",
}

# Unicode script ranges
_SCRIPTS = {
    "bn": (0x0980, 0x09FF),
    "te": (0x0C00, 0x0C7F),
    "ta": (0x0B80, 0x0BFF),
    "devanagari": (0x0900, 0x097F),  # hi or mr - disambiguated below
}

# Frequent function words that separate Hindi from Marathi in Devanagari.
_HI_MARKERS = ["है", "हैं", "और", "के लिए", "का ", "की ", "के ", "किराया", "किरायेदार", "महीना", "नहीं"]
_MR_MARKERS = ["आहे", "आहेत", "आणि", "साठी", "चा ", "ची ", "चे ", "भाडे", "भाडेकरू", "महिना", "नाही"]


def detect_language(text):
    """Detect one of en/hi/bn/mr/te/ta from Unicode script + marker words."""
    if not text:
        return "en"
    counts = {key: 0 for key in _SCRIPTS}
    for char in text:
        code = ord(char)
        for script, (low, high) in _SCRIPTS.items():
            if low <= code <= high:
                counts[script] += 1
    dominant = max(counts, key=counts.get)
    if counts[dominant] < max(10, len(text) * 0.05):
        return "en"
    if dominant != "devanagari":
        return dominant
    hindi_score = sum(text.count(marker) for marker in _HI_MARKERS)
    marathi_score = sum(text.count(marker) for marker in _MR_MARKERS)
    return "mr" if marathi_score > hindi_score else "hi"


# ---------------------------------------------------------------------------
# Legal/rental domain glossary. Keyed by English; order within each value is
# (hi, bn, mr, te, ta). Multi-word phrases listed before single words is not
# required - the engine sorts by length at build time.
# ---------------------------------------------------------------------------

GLOSSARY = {
    "rent agreement": ("किराया समझौता", "ভাড়ার চুক্তি", "भाडे करार", "అద్దె ఒప్పందం", "வாடகை ஒப்பந்தம்"),
    "leave and license agreement": ("लीव एंड लाइसेंस समझौता", "লিভ অ্যান্ড লাইসেন্স চুক্তি", "लीव्ह अँड लायसन्स करार", "లీవ్ అండ్ లైసెన్స్ ఒప్పందం", "லீவ் அண்ட் லைசென்ஸ் ஒப்பந்தம்"),
    "security deposit": ("जमानत राशि", "জামানত", "अनामत रक्कम", "సెక్యూరిటీ డిపాజిట్", "பாதுகாப்பு வைப்புத்தொகை"),
    "monthly rent": ("मासिक किराया", "মাসিক ভাড়া", "मासिक भाडे", "నెలవారీ అద్దె", "மாத வாடகை"),
    "notice period": ("नोटिस अवधि", "নোটিশের মেয়াদ", "नोटीस कालावधी", "నోటీసు వ్యవధి", "அறிவிப்பு காலம்"),
    "late fee": ("विलंब शुल्क", "বিলম্ব ফি", "विलंब शुल्क", "ఆలస్య రుసుము", "தாமதக் கட்டணம்"),
    "grace period": ("रियायती अवधि", "অতিরিক্ত সময়", "सवलत कालावधी", "గడువు వ్యవధి", "சலுகைக் காலம்"),
    "lock-in period": ("लॉक-इन अवधि", "লক-ইন মেয়াদ", "लॉक-इन कालावधी", "లాక్-ఇన్ వ్యవధి", "லாக்-இன் காலம்"),
    "due date": ("नियत तिथि", "নির্ধারিত তারিখ", "देय तारीख", "గడువు తేదీ", "உரிய தேதி"),
    "stamp duty": ("स्टांप शुल्क", "স্ট্যাম্প শুল্ক", "मुद्रांक शुल्क", "స్టాంపు సుంకం", "முத்திரைத் தீர்வை"),
    "normal wear and tear": ("सामान्य टूट-फूट", "স্বাভাবিক ক্ষয়ক্ষতি", "सामान्य झीज", "సాధారణ అరుగుదల", "இயல்பான தேய்மானம்"),
    "without notice": ("बिना नोटिस", "নোটিশ ছাড়া", "नोटीसशिवाय", "నోటీసు లేకుండా", "அறிவிப்பு இல்லாமல்"),
    "for any reason": ("किसी भी कारण से", "যেকোনো কারণে", "कोणत्याही कारणास्तव", "ఏ కారణంతోనైనా", "எந்தக் காரணத்திற்காகவும்"),
    "at any time": ("किसी भी समय", "যেকোনো সময়", "कोणत्याही वेळी", "ఎప్పుడైనా", "எப்போது வேண்டுமானாலும்"),
    "non-refundable": ("गैर-वापसी योग्य", "অফেরতযোগ্য", "परत न करण्यायोग्य", "తిరిగి చెల్లించని", "திரும்பப்பெற முடியாத"),
    "refundable": ("वापसी योग्य", "ফেরতযোগ্য", "परत करण्यायोग्य", "తిరిగి చెల్లించదగిన", "திரும்பப்பெறத்தக்க"),
    "per day": ("प्रति दिन", "প্রতিদিন", "प्रति दिवस", "రోజుకు", "ஒரு நாளைக்கு"),
    "shall pay": ("भुगतान करेगा", "পরিশোধ করবে", "भरेल", "చెల్లించాలి", "செலுத்த வேண்டும்"),
    "shall not": ("नहीं करेगा", "করবে না", "करणार नाही", "చేయకూడదు", "கூடாது"),
    "written permission": ("लिखित अनुमति", "লিখিত অনুমতি", "लेखी परवानगी", "వ్రాతపూర్వక అనుమతి", "எழுத்துப்பூர்வ அனுமதி"),
    "agreement": ("समझौता", "চুক্তি", "करार", "ఒప్పందం", "ஒப்பந்தம்"),
    "lease": ("पट्टा", "ইজারা", "भाडेपट्टा", "లీజు", "குத்தகை"),
    "landlord": ("मकान मालिक", "বাড়িওয়ালা", "घरमालक", "ఇంటి యజమాని", "வீட்டு உரிமையாளர்"),
    "lessor": ("पट्टादाता", "ইজারাদাতা", "भाडेपट्टा देणारा", "లీజుదారు (యజమాని)", "குத்தகை வழங்குபவர்"),
    "tenant": ("किरायेदार", "ভাড়াটে", "भाडेकरू", "అద్దెదారు", "வாடகைதாரர்"),
    "lessee": ("पट्टेदार", "ইজারা গ্রহীতা", "भाडेपट्टा घेणारा", "లీజు తీసుకున్నవారు", "குத்தகைதாரர்"),
    "licensee": ("अनुज्ञप्तिधारी", "লাইসেন্সধারী", "परवानाधारक", "లైసెన్సీ", "உரிமம் பெற்றவர்"),
    "licensor": ("अनुज्ञापक", "লাইসেন্সদাতা", "परवाना देणारा", "లైసెన్సర్", "உரிமம் வழங்குபவர்"),
    "rent": ("किराया", "ভাড়া", "भाडे", "అద్దె", "வாடகை"),
    "deposit": ("जमा राशि", "আমানত", "ठेव", "డిపాజిట్", "வைப்புத்தொகை"),
    "premises": ("परिसर", "প্রাঙ্গণ", "जागा", "ఆవరణ", "வளாகம்"),
    "property": ("संपत्ति", "সম্পত্তি", "मालमत्ता", "ఆస్తి", "சொத்து"),
    "notice": ("नोटिस", "নোটিশ", "नोटीस", "నోటీసు", "அறிவிப்பு"),
    "months": ("महीने", "মাস", "महिने", "నెలలు", "மாதங்கள்"),
    "month": ("महीना", "মাস", "महिना", "నెల", "மாதம்"),
    "days": ("दिनों", "দিন", "दिवस", "రోజులు", "நாட்கள்"),
    "day": ("दिन", "দিন", "दिवस", "రోజు", "நாள்"),
    "year": ("वर्ष", "বছর", "वर्ष", "సంవత్సరం", "ஆண்டு"),
    "eviction": ("बेदखली", "উচ্ছেদ", "निष्कासन", "తొలగింపు", "வெளியேற்றம்"),
    "evict": ("बेदखल करना", "উচ্ছেদ করা", "निष्कासित करणे", "తొలగించు", "வெளியேற்று"),
    "termination": ("समाप्ति", "সমাপ্তি", "समाप्ती", "రద్దు", "முடிவு"),
    "terminate": ("समाप्त करना", "সমাপ্ত করা", "समाप्त करणे", "రద్దు చేయు", "முடிவுக்குக் கொண்டுவரு"),
    "renewal": ("नवीनीकरण", "নবায়ন", "नूतनीकरण", "పునరుద్ధరణ", "புதுப்பித்தல்"),
    "renew": ("नवीनीकरण करना", "নবায়ন করা", "नूतनीकरण करणे", "పునరుద్ధరించు", "புதுப்பி"),
    "repairs": ("मरम्मत", "মেরামত", "दुरुस्ती", "మరమ్మతులు", "பழுதுகள்"),
    "repair": ("मरम्मत", "মেরামত", "दुरुस्ती", "మరమ్మతు", "பழுது"),
    "maintenance": ("रखरखाव", "রক্ষণাবেক্ষণ", "देखभाल", "నిర్వహణ", "பராமரிப்பு"),
    "structural": ("संरचनात्मक", "কাঠামোগত", "संरचनात्मक", "నిర్మాణపరమైన", "கட்டமைப்பு"),
    "entry": ("प्रवेश", "প্রবেশ", "प्रवेश", "ప్రవేశం", "நுழைவு"),
    "enter": ("प्रवेश करना", "প্রবেশ করা", "प्रवेश करणे", "ప్రవేశించు", "நுழை"),
    "permission": ("अनुमति", "অনুমতি", "परवानगी", "అనుమతి", "அனுமதி"),
    "written": ("लिखित", "লিখিত", "लेखी", "వ్రాతపూర్వక", "எழுத்துப்பூர்வ"),
    "forfeited": ("जब्त", "বাজেয়াপ্ত", "जप्त", "జప్తు", "பறிமுதல்"),
    "forfeit": ("जब्त करना", "বাজেয়াপ্ত করা", "जप्त करणे", "జప్తు చేయు", "பறிமுதல் செய்"),
    "fine": ("जुर्माना", "জরিমানা", "दंड", "జరిమానా", "அபராதம்"),
    "penalty": ("दंड", "জরিমানা", "दंड", "జరిమానా", "அபராதம்"),
    "payment": ("भुगतान", "পরিশোধ", "भरणा", "చెల్లింపు", "கட்டணம்"),
    "advance": ("अग्रिम", "অগ্রিম", "आगाऊ", "అడ్వాన్సు", "முன்பணம்"),
    "utilities": ("बिजली-पानी सेवाएँ", "ইউটিলিটি পরিষেবা", "उपयोगिता सेवा", "యుటిలిటీలు", "பயன்பாட்டு சேவைகள்"),
    "electricity": ("बिजली", "বিদ্যুৎ", "वीज", "విద్యుత్", "மின்சாரம்"),
    "water": ("पानी", "জল", "पाणी", "నీరు", "தண்ணீர்"),
    "guests": ("अतिथि", "অতিথিরা", "पाहुणे", "అతిథులు", "விருந்தினர்கள்"),
    "guest": ("अतिथि", "অতিথি", "पाहुणा", "అతిథి", "விருந்தினர்"),
    "arbitration": ("मध्यस्थता", "সালিশ", "लवाद", "మధ్యవర్తిత్వం", "நடுவர் தீர்ப்பு"),
    "arbitrator": ("मध्यस्थ", "সালিশকারী", "लवाद", "మధ్యవర్తి", "நடுவர்"),
    "dispute": ("विवाद", "বিরোধ", "वाद", "వివాదం", "தகராறு"),
    "court": ("अदालत", "আদালত", "न्यायालय", "కోర్టు", "நீதிமன்றம்"),
    "legal": ("कानूनी", "আইনি", "कायदेशीर", "చట్టపరమైన", "சட்டப்பூர்வ"),
    "law": ("कानून", "আইন", "कायदा", "చట్టం", "சட்டம்"),
    "rights": ("अधिकार", "অধিকার", "हक्क", "హక్కులు", "உரிமைகள்"),
    "waive": ("त्यागना", "পরিত্যাগ করা", "सोडून देणे", "వదులుకొను", "விட்டுக்கொடு"),
    "waiver": ("अधिकार-त्याग", "অধিকার পরিত্যাগ", "हक्कत्याग", "హక్కు వదులుకోవడం", "உரிமை துறப்பு"),
    "government": ("सरकार", "সরকার", "सरकार", "ప్రభుత్వం", "அரசு"),
    "authority": ("प्राधिकरण", "কর্তৃপক্ষ", "प्राधिकरण", "అధికార సంస్థ", "அதிகாரம்"),
    "complaint": ("शिकायत", "অভিযোগ", "तक्रार", "ఫిర్యాదు", "புகார்"),
    "inspection": ("निरीक्षण", "পরিদর্শন", "तपासणी", "తనిఖీ", "ஆய்வு"),
    "damage": ("क्षति", "ক্ষতি", "नुकसान", "నష్టం", "சேதம்"),
    "vacate": ("खाली करना", "খালি করা", "रिकामे करणे", "ఖాళీ చేయు", "காலி செய்"),
    "possession": ("कब्जा", "দখল", "ताबा", "స్వాధీనం", "உடைமை"),
    "registration": ("पंजीकरण", "নিবন্ধন", "नोंदणी", "నమోదు", "பதிவு"),
    "witness": ("गवाह", "সাক্ষী", "साक्षीदार", "సాక్షి", "சாட்சி"),
    "signature": ("हस्ताक्षर", "স্বাক্ষর", "स्वाक्षरी", "సంతకం", "கையொப்பம்"),
    "parties": ("पक्षकार", "পক্ষগণ", "पक्षकार", "పక్షాలు", "தரப்பினர்"),
    "clause": ("खंड", "ধারা", "कलम", "నిబంధన", "பிரிவு"),
    "sublet": ("उप-किराए पर देना", "উপ-ভাড়া দেওয়া", "पोट-भाड्याने देणे", "ఉప అద్దెకు ఇచ్చు", "துணை வாடகைக்கு விடு"),
    "pets": ("पालतू जानवर", "পোষা প্রাণী", "पाळीव प्राणी", "పెంపుడు జంతువులు", "செல்லப் பிராணிகள்"),
    "immediately": ("तुरंत", "অবিলম্বে", "ताबडतोब", "వెంటనే", "உடனடியாக"),
    "refund": ("वापसी", "ফেরত", "परतावा", "తిరిగి చెల్లింపు", "பணத்திரும்பல்"),
    "increase": ("वृद्धि", "বৃদ্ধি", "वाढ", "పెంపు", "உயர்வு"),
    "overnight": ("रात भर", "রাতভর", "रात्रभर", "రాత్రంతా", "இரவு முழுவதும்"),
    "habitability": ("रहने योग्य स्थिति", "বাসযোগ্যতা", "राहण्यायोग्य स्थिती", "నివాసయోగ్యత", "வசிப்பதற்கேற்ற நிலை"),
    "jurisdiction": ("क्षेत्राधिकार", "এখতিয়ার", "अधिकारक्षेत्र", "అధికార పరిధి", "அதிகார வரம்பு"),
}

_LANG_INDEX = {"hi": 0, "bn": 1, "mr": 2, "te": 3, "ta": 4}


@lru_cache(maxsize=None)
def _table(source, target):
    """Ordered (longest-first) replacement table for a language pair with
    English as one side."""
    entries = []
    if source == "en":
        index = _LANG_INDEX[target]
        for english, forms in GLOSSARY.items():
            entries.append((english, forms[index]))
    else:
        index = _LANG_INDEX[source]
        for english, forms in GLOSSARY.items():
            entries.append((forms[index], english))
    entries.sort(key=lambda pair: len(pair[0]), reverse=True)
    return tuple(entries)


def _apply_table(text, table, source_is_english):
    for source_term, target_term in table:
        if source_is_english:
            pattern = re.compile(r"\b" + re.escape(source_term) + r"\b", re.IGNORECASE)
            text = pattern.sub(target_term, text)
        else:
            text = text.replace(source_term, target_term)
    return text


# ---------------------------------------------------------------------------
# Optional neural backend (argostranslate). Fully offline once installed.
# ---------------------------------------------------------------------------

def _neural_translate(text, source, target):
    """Returns translated text or None if the local model isn't installed."""
    try:
        import argostranslate.translate as argos
    except ImportError:
        return None
    try:
        installed = argos.get_installed_languages()
        source_lang = next((l for l in installed if l.code == source), None)
        target_lang = next((l for l in installed if l.code == target), None)
        if not source_lang or not target_lang:
            return None
        translation = source_lang.get_translation(target_lang)
        if translation is None:
            return None
        return translation.translate(text)
    except Exception:
        return None


def translate(text, target, source=None):
    """Translate text between any two of en/hi/bn/mr/te/ta.

    Returns dict: translated text, detected source, engine used, and the
    glossary rows that applied (for display).
    """
    if not text or not text.strip():
        return {"text": "", "source": source or "en", "target": target, "engine": "none", "glossary": []}

    source = source or detect_language(text)
    if source not in LANGUAGES or target not in LANGUAGES:
        raise ValueError(f"Unsupported language: {source}->{target}")

    if source == target:
        return {"text": text, "source": source, "target": target, "engine": "identity", "glossary": []}

    # Try neural first (direct, then pivot through English)
    neural = _neural_translate(text, source, target)
    if neural is not None:
        return {"text": neural, "source": source, "target": target, "engine": "neural", "glossary": []}
    if source != "en" and target != "en":
        step = _neural_translate(text, source, "en")
        if step is not None:
            final = _neural_translate(step, "en", target)
            if final is not None:
                return {"text": final, "source": source, "target": target, "engine": "neural (via English)", "glossary": []}

    # Lexicon engine, pivoting via English when neither side is English
    matched = []
    result = text
    if source == "en":
        table = _table("en", target)
        matched = [(a, b) for a, b in table if re.search(r"\b" + re.escape(a) + r"\b", text, re.IGNORECASE)]
        result = _apply_table(result, table, source_is_english=True)
    elif target == "en":
        table = _table(source, "en")
        matched = [(a, b) for a, b in table if a in text]
        result = _apply_table(result, table, source_is_english=False)
    else:
        to_english = _table(source, "en")
        matched = [(a, b) for a, b in to_english if a in text]
        result = _apply_table(result, to_english, source_is_english=False)
        result = _apply_table(result, _table("en", target), source_is_english=True)

    return {"text": result, "source": source, "target": target, "engine": "lexicon", "glossary": matched[:40]}


def to_english_for_analysis(text):
    """Convert an Indic-language agreement to analyzable English.
    Returns (english_text, detected_language)."""
    language = detect_language(text)
    if language == "en":
        return text, "en"
    result = translate(text, target="en", source=language)
    return result["text"], language
