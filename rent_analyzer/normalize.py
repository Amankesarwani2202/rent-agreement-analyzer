"""Typed normalizers: money, durations, rent multiples, number words.

Every parser is format-tolerant: digits, words ("two thousand"), Indian
grouping (2,50,000), Rs./INR/rupees forms, and the legal "sixty (60) days"
convention.
"""

import re

UNITS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
    "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19,
    "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,
    "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
}
SCALES = {
    "hundred": 100,
    "thousand": 1000,
    "lakh": 100000,
    "lakhs": 100000,
    "lac": 100000,
    "lacs": 100000,
    "million": 1000000,
    "crore": 10000000,
    "crores": 10000000,
}

_NUMBER_WORD = r"(?:zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred|thousand|lakhs?|lacs?|million|crores?|and|[-\s])+"


def words_to_number(phrase):
    """'two thousand five hundred' -> 2500; 'one lakh twenty thousand' -> 120000."""
    tokens = re.split(r"[\s-]+", phrase.lower().strip())
    total = 0
    current = 0
    seen_any = False
    for token in tokens:
        if token in ("and", ""):
            continue
        if token in UNITS:
            current += UNITS[token]
            seen_any = True
        elif token in SCALES:
            scale = SCALES[token]
            if current == 0:
                current = 1
            if scale >= 1000:
                total += current * scale
                current = 0
            else:
                current *= scale
            seen_any = True
        else:
            return None
    if not seen_any:
        return None
    return total + current


def _digits_to_number(raw):
    return float(raw.replace(",", "")) if "." in raw else int(raw.replace(",", ""))


def parse_money(text):
    """Return list of {value, currency, span, text} for every money mention.

    Handles: $2,400 | ₹25,000 | Rs. 30,000/- | INR 42000 | 2,50,000 (Indian
    grouping) | 'rupees twenty five thousand' | 'two hundred dollars'.
    """
    results = []
    seen_spans = []

    def overlaps(span):
        return any(not (span[1] <= s or span[0] >= e) for s, e in seen_spans)

    def add(value, currency, match, group=0):
        span = match.span(group)
        if value is None or overlaps(span):
            return
        seen_spans.append(span)
        results.append({"value": value, "currency": currency, "span": span, "text": match.group(group).strip()})

    # Symbol/abbreviation + digits
    for match in re.finditer(r"(₹|\$|(?:Rs\.?|INR|USD)\s?)\s*([\d][\d,]*(?:\.\d{1,2})?)(?:\s*/-)?", text, re.IGNORECASE):
        symbol = match.group(1).strip().rstrip(".").upper()
        currency = "INR" if symbol in ("₹", "RS", "INR") else "USD"
        add(_digits_to_number(match.group(2)), currency, match)

    # 'rupees <words or digits>'
    for match in re.finditer(r"\b(?:rupees|rs\.?)\s+(" + _NUMBER_WORD + r")", text, re.IGNORECASE):
        value = words_to_number(match.group(1))
        add(value, "INR", match)

    # '<words> dollars/rupees'
    for match in re.finditer(r"\b(" + _NUMBER_WORD + r")\s*(dollars|rupees)\b", text, re.IGNORECASE):
        value = words_to_number(match.group(1))
        currency = "USD" if match.group(2).lower() == "dollars" else "INR"
        add(value, currency, match)

    results.sort(key=lambda item: item["span"][0])
    return results


_DURATION_UNIT_DAYS = {"hour": 1 / 24, "day": 1, "night": 1, "week": 7, "fortnight": 14, "month": 30, "year": 365}


def parse_durations(text):
    """Return list of {days, span, text} for every duration mention.

    Handles: 30 days | sixty (60) days | two months | 48 hours | one year |
    'sixty days' | a fortnight.
    """
    results = []
    pattern = (
        r"\b(\d+|" + _NUMBER_WORD + r")\s*(?:\((\d+)\))?\s*"
        r"(hours?|days?|nights?|weeks?|months?|years?)\b"
    )
    for match in re.finditer(pattern, text, re.IGNORECASE):
        raw = match.group(1).strip()
        if raw.isdigit():
            amount = int(raw)
        else:
            amount = words_to_number(raw)
        # Prefer parenthesized numeral if present (legal convention)
        if match.group(2):
            paren = int(match.group(2))
            if amount is None:
                amount = paren
            elif amount != paren:
                amount = paren  # numeral usually controls; mismatch itself is a flag (later phase)
        if amount is None:
            continue
        unit = match.group(3).lower().rstrip("s")
        days = amount * _DURATION_UNIT_DAYS[unit]
        results.append({"days": days, "span": match.span(), "text": match.group(0).strip(), "unit": unit, "amount": amount})

    for match in re.finditer(r"\ba fortnight\b", text, re.IGNORECASE):
        results.append({"days": 14.0, "span": match.span(), "text": match.group(0), "unit": "fortnight", "amount": 1})

    results.sort(key=lambda item: item["span"][0])
    return results


def duration_near(text, anchor_words, max_distance=120, allowed_units=None):
    """Duration closest to any anchor word (e.g. 'notice'), within a
    character window. Returns days (float) or None.

    allowed_units restricts matches (e.g. {'day','week'} so \"two months'
    rent\" is never misread as a 60-day window)."""
    durations = parse_durations(text)
    if allowed_units:
        durations = [d for d in durations if d["unit"] in allowed_units]
    if not durations:
        return None
    low = text.lower()
    anchors = []
    for word in anchor_words:
        for match in re.finditer(re.escape(word.lower()), low):
            anchors.append(match.start())
    if not anchors:
        return None
    best = None
    best_distance = None
    for duration in durations:
        mid = (duration["span"][0] + duration["span"][1]) / 2
        distance = min(abs(mid - a) for a in anchors)
        if distance <= max_distance and (best_distance is None or distance < best_distance):
            best = duration
            best_distance = distance
    return best["days"] if best else None


def months_of_rent(text):
    """\"six months' rent\" / '3 months rent' -> number of months, else None."""
    match = re.search(
        r"\b(\d+|" + _NUMBER_WORD + r")\s*months?[’']?s?\s*(?:of\s+)?(?:rent|licen[cs]e fee)\b",
        text,
        re.IGNORECASE,
    )
    if not match:
        return None
    raw = match.group(1).strip()
    if raw.isdigit():
        return int(raw)
    return words_to_number(raw)
