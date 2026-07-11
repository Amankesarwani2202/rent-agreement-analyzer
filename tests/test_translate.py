# -*- coding: utf-8 -*-
import itertools

import pytest

from rent_analyzer.translate import LANGUAGES, detect_language, to_english_for_analysis, translate

HINDI = "मकान मालिक और किरायेदार के बीच किराया समझौता। मासिक किराया और जमानत राशि देय है।"
BENGALI = "বাড়িওয়ালা ও ভাড়াটের মধ্যে ভাড়ার চুক্তি। মাসিক ভাড়া এবং জামানত প্রদেয়।"
MARATHI = "घरमालक आणि भाडेकरू यांच्यात भाडे करार आहे. मासिक भाडे देय आहे."
TELUGU = "ఇంటి యజమాని మరియు అద్దెదారు మధ్య అద్దె ఒప్పందం. నెలవారీ అద్దె చెల్లించాలి."
TAMIL = "வீட்டு உரிமையாளர் மற்றும் வாடகைதாரர் இடையே வாடகை ஒப்பந்தம். மாத வாடகை செலுத்த வேண்டும்."
ENGLISH = "This rent agreement between the landlord and tenant sets the monthly rent and security deposit."


def test_detect_all_languages():
    assert detect_language(ENGLISH) == "en"
    assert detect_language(HINDI) == "hi"
    assert detect_language(BENGALI) == "bn"
    assert detect_language(MARATHI) == "mr"
    assert detect_language(TELUGU) == "te"
    assert detect_language(TAMIL) == "ta"


def test_en_to_hi_key_terms():
    result = translate("The tenant shall pay the monthly rent and security deposit.", target="hi")
    assert "किरायेदार" in result["text"]
    assert "मासिक किराया" in result["text"]
    assert "जमानत राशि" in result["text"]


def test_hi_to_en():
    result = translate(HINDI, target="en")
    assert "landlord" in result["text"]
    assert "rent agreement" in result["text"]


def test_indic_to_indic_pivots():
    result = translate(HINDI, target="ta")
    assert "வாடகை" in result["text"]  # rent
    assert result["source"] == "hi"


@pytest.mark.parametrize("src,tgt", list(itertools.permutations(LANGUAGES.keys(), 2)))
def test_all_30_pairs_run(src, tgt):
    samples = {"en": ENGLISH, "hi": HINDI, "bn": BENGALI, "mr": MARATHI, "te": TELUGU, "ta": TAMIL}
    result = translate(samples[src], target=tgt, source=src)
    assert result["text"].strip()
    assert result["target"] == tgt


def test_numbers_and_currency_preserved():
    result = translate("The monthly rent is ₹25,000 due on the 5th day.", target="hi")
    assert "₹25,000" in result["text"]
    assert "5" in result["text"]


def test_unknown_words_pass_through():
    result = translate("The tenant Robert shall pay rent.", target="hi")
    assert "Robert" in result["text"]


def test_same_language_identity():
    result = translate(ENGLISH, target="en", source="en")
    assert result["text"] == ENGLISH


def test_hindi_agreement_analyzable():
    text, language = to_english_for_analysis("जमानत राशि गैर-वापसी योग्य है और मकान मालिक बिना नोटिस प्रवेश कर सकता है।")
    assert language == "hi"
    assert "non-refundable" in text.lower()
    assert "without notice" in text.lower()
