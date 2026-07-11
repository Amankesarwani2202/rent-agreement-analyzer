from rent_analyzer.normalize import duration_near, months_of_rent, parse_durations, parse_money, words_to_number


def test_words_simple():
    assert words_to_number("two thousand") == 2000
    assert words_to_number("twenty five") == 25
    assert words_to_number("fifty thousand") == 50000


def test_words_indian_scales():
    assert words_to_number("one lakh") == 100000
    assert words_to_number("one lakh twenty thousand") == 120000


def test_words_invalid():
    assert words_to_number("banana") is None


def test_money_symbol():
    result = parse_money("rent of $2,400 per month")
    assert result[0]["value"] == 2400 and result[0]["currency"] == "USD"


def test_money_rs_slash():
    result = parse_money("deposit of Rs. 30,000/- payable")
    assert result[0]["value"] == 30000 and result[0]["currency"] == "INR"


def test_money_inr_prefix():
    result = parse_money("INR 42,000 monthly")
    assert result[0]["value"] == 42000 and result[0]["currency"] == "INR"


def test_money_indian_grouping():
    result = parse_money("₹2,50,000 as deposit")
    assert result[0]["value"] == 250000


def test_money_words():
    result = parse_money("a fine of rupees two thousand per day")
    assert result[0]["value"] == 2000 and result[0]["currency"] == "INR"


def test_duration_digits():
    assert parse_durations("within 21 days")[0]["days"] == 21


def test_duration_words():
    assert parse_durations("within sixty days")[0]["days"] == 60


def test_duration_legal_parenthetical():
    assert parse_durations("sixty (60) days notice")[0]["days"] == 60


def test_duration_hours():
    assert parse_durations("48 hours notice")[0]["days"] == 2


def test_duration_word_months():
    assert parse_durations("two months notice")[0]["days"] == 60


def test_duration_near_picks_closest():
    text = "the lease term is 12 months and either party may give 30 days notice"
    assert duration_near(text, ["notice"]) == 30


def test_duration_near_unit_filter():
    text = "deposit equal to two months' rent returned within 14 days of vacating"
    assert duration_near(text, ["returned"], allowed_units={"day"}) == 14


def test_months_of_rent():
    assert months_of_rent("deposit equivalent to six months' rent") == 6
    assert months_of_rent("deposit of 3 months rent") == 3
    assert months_of_rent("no multiple here") is None
