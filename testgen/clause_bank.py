"""Labeled clause templates for synthetic rent agreements.

Each template:
  text     - clause text with {placeholders}
  expect   - categories the analyzer MUST flag for this clause (empty = safe;
             the clause must NOT trigger any flag)
  params   - generator fills placeholders from these pools

Safe templates are as important as traps: they are the false-positive tests.
Deliberately includes phrasing the current analyzer is known to miss or
mis-flag (legalese, numbers as words, negation, landlord-side obligations).
"""

# Placeholder pools. {L}/{T} are party names, swapped by the perturber.
POOLS = {
    "rent_usd": ["$1,800", "$2,400", "$3,100"],
    "rent_inr": ["₹25,000", "Rs. 30,000/-", "INR 42,000", "rupees twenty five thousand"],
    # Must exceed deposit_max_months in EVERY jurisdiction (strictest allows 6)
    "dep_multiple_high": ["eight", "ten", "twelve"],
    "dep_multiple_ok": ["one", "two"],
    "grace_days": ["3", "5", "7"],
    "small_fee": ["$25", "$50", "₹500"],
    "big_fee": ["$150", "$200", "₹2,000", "rupees two thousand"],
    "notice_ok": ["30 days", "60 days", "one month", "two months"],
    "notice_short": ["24 hours", "48 hours", "two days"],
    "return_days_ok": ["14", "21"],
}

CLAUSE_BANK = {
    "rent_increase": {
        "safe": [
            "Any rent increase shall require at least {notice_ok} prior written notice to the {T} and shall not exceed once per year.",
            "The rent shall stand increased by 5% on each anniversary of this agreement, as agreed by both parties.",
        ],
        "trap": [
            {
                "text": "Rent may be enhanced at any time at the absolute discretion of the {L}.",
                "expect": ["rent_increase"],
            },
            {
                "text": "The {L} may revise the rent as per market rate at any time during the term.",
                "expect": ["rent_increase"],
            },
            {
                "text": "Rent may be revised as per market rate at any time during the term.",
                "expect": ["rent_increase"],
            },
        ],
    },
    "deposit": {
        "safe": [
            "The {T} shall pay a security deposit of {rent_usd}, which is fully refundable and shall be returned within {return_days_ok} days of vacating, less lawful deductions for damage beyond normal wear and tear.",
            "The {T} shall place a refundable security deposit equal to {dep_multiple_ok} months' rent with the {L}, refundable at the end of the tenancy.",
            "The interest-free refundable security deposit of {rent_inr} shall be returned to the {T} within {return_days_ok} days of handover of vacant possession.",
        ],
        "trap": [
            {
                "text": "The {T} shall pay {rent_usd} as a non-refundable security deposit.",
                "expect": ["deposit"],
            },
            {
                "text": "The {T} shall deposit an amount equivalent to {dep_multiple_high} months' rent as security deposit with the {L}.",
                "expect": ["deposit"],
            },
            {
                "text": "The entire security deposit shall stand forfeited if the {T} vacates the premises before expiry of the lock-in period for any reason whatsoever.",
                "expect": ["deposit"],
            },
            {
                "text": "The security deposit of {rent_inr} shall be retained by the {L} and shall not be returned under any circumstances.",
                "expect": ["deposit"],
            },
            {
                "text": "The security deposit shall in no event be refunded to the {T}.",
                "expect": ["deposit"],
            },
        ],
    },
    "late_fee": {
        "safe": [
            "A late fee of {small_fee} applies if rent is received more than {grace_days} days after the due date, following the grace period.",
            "If rent remains unpaid for {grace_days} days after the due date, a one-time late charge of {small_fee} shall apply, capped at that amount per month.",
        ],
        "trap": [
            {
                "text": "A late fee of {big_fee} per day shall apply to any rent received after the due date.",
                "expect": ["late_fee"],
            },
            {
                "text": "Delayed payment of rent shall attract a daily fine of {big_fee} without any grace period.",
                "expect": ["late_fee"],
            },
        ],
    },
    "entry": {
        "safe": [
            "The {L} shall provide at least 24 hours written notice before entering the premises, except in case of emergency.",
            "The {L} shall not enter the premises without prior notice to the {T}, save in the event of fire, flood or other emergency.",
            "The {L} may inspect the premises upon 48 hours advance intimation to the {T} at a mutually convenient time.",
        ],
        "trap": [
            {
                "text": "The {L} may enter the premises at any time without notice for inspection or any other purpose.",
                "expect": ["entry"],
            },
            {
                "text": "The {L} shall retain a master key and may access the premises day or night at his sole discretion.",
                "expect": ["entry"],
            },
            {
                "text": "The {L} or his agents may enter upon the premises without prior notice to the {T} at any hour.",
                "expect": ["entry"],
            },
            {
                "text": "The {L} reserves the right of entry to the demised premises at all hours without any intimation to the {T}.",
                "expect": ["entry"],
            },
        ],
    },
    "eviction": {
        "safe": [
            "Either party may terminate this agreement at the end of the term by providing {notice_ok} written notice to the other party.",
            "In case of breach, the {L} may terminate this agreement after giving {notice_ok} notice in writing and following due legal process for eviction.",
            "The {T} may vacate the premises upon {notice_ok} prior written notice to the {L}.",
        ],
        "trap": [
            {
                "text": "The {L} may terminate this lease at any time for any reason with {notice_short} notice, and the {T} must vacate immediately.",
                "expect": ["eviction"],
            },
            {
                "text": "Upon default, the {L} may without recourse to court lock the premises, disconnect utilities and remove the belongings of the {T}.",
                "expect": ["eviction"],
            },
            {
                "text": "The {L} may require the {T} to quit and deliver up vacant possession of the premises within {notice_short} at the sole discretion of the {L}.",
                "expect": ["eviction"],
            },
        ],
    },
    "waiver": {
        "safe": [
            "The {L} agrees to waive the late fee for the first instance of delayed payment in any calendar year.",
            "No failure by either party to enforce any provision hereof shall constitute a waiver of that provision.",
        ],
        "trap": [
            {
                "text": "The {T} waives the right to a jury trial and any right to counterclaim in any proceeding brought by the {L}.",
                "expect": ["waiver"],
            },
            {
                "text": "The {T} hereby waives all rights and protections available under any rent control or tenant protection legislation.",
                "expect": ["waiver"],
            },
            {
                "text": "The {T} relinquishes any claim to the warranty of habitability and accepts the premises strictly as-is.",
                "expect": ["waiver", "repairs"],
            },
        ],
    },
    "arbitration": {
        "safe": [
            "Any dispute shall be referred to a sole arbitrator appointed mutually by both parties, with costs shared equally.",
            "Disputes shall be subject to the jurisdiction of the courts at the location of the premises.",
        ],
        "trap": [
            {
                "text": "All disputes shall be decided by an arbitrator selected solely by the {L}, and the {T} shall bear the entire cost of arbitration.",
                "expect": ["arbitration"],
            },
        ],
    },
    "penalty": {
        "safe": [
            "No penalty shall apply if the {T} terminates early after serving the agreed notice period.",
            "Neither party shall be liable for any fine or penalty arising from events beyond their reasonable control.",
        ],
        "trap": [
            {
                "text": "A penalty of {big_fee} per nail hole or wall mark shall be deducted from the deposit at move-out.",
                "expect": ["penalty"],
            },
            {
                "text": "Breach of any house rule shall attract a fine of {big_fee} per occurrence as determined by the {L}.",
                "expect": ["penalty"],
            },
            {
                "text": "A charge of {small_fee} per nail hole or wall fixture mark shall be deducted from the deposit at move-out.",
                "expect": ["penalty"],
            },
        ],
    },
    "repairs": {
        "safe": [
            "The {L} is responsible for structural repairs and for maintaining the premises in habitable condition, while the {T} handles minor day-to-day upkeep.",
            "Major repairs including the roof and structural elements shall be carried out by the {L} at his own cost.",
            "The {T} shall keep the interiors clean and bear the cost of minor repairs up to {small_fee}.",
        ],
        "trap": [
            {
                "text": "The {T} shall be responsible for all repairs including structural repairs, roof repairs and habitability issues at the {T}'s own expense.",
                "expect": ["repairs"],
            },
            {
                "text": "All major repairs and structural maintenance of the premises shall be borne solely by the {T}.",
                "expect": ["repairs"],
            },
        ],
    },
    "guest_policy": {
        "safe": [
            "Guests of the {T} may stay at the premises for up to 14 consecutive nights without prior approval.",
            "The {T} may host visitors, provided long-term occupants beyond 30 days are added to the agreement.",
        ],
        "trap": [
            {
                "text": "No guest shall stay overnight in the premises without the prior written permission of the {L}.",
                "expect": ["guest_policy"],
            },
            {
                "text": "Guests may not stay more than one night per month, and any guest stay requires advance written approval of the {L}.",
                "expect": ["guest_policy"],
            },
        ],
    },
    "government_contact": {
        "safe": [
            "The {L} confirms that the premises comply with all applicable government and municipal authority regulations.",
            "Each party shall cooperate with any lawful inquiry by a government authority concerning the premises.",
        ],
        "trap": [
            {
                "text": "The {T} shall not approach any government authority or housing inspector with any complaint regarding the premises, and any such contact shall be grounds for immediate eviction.",
                "expect": ["government_contact"],
            },
        ],
    },
    "renewal": {
        "safe": [
            "This agreement may be renewed on mutually agreed terms, with either party giving {notice_ok} notice of its intention.",
            "Upon expiry, the tenancy shall continue month-to-month unless either party gives {notice_ok} notice.",
        ],
        "trap": [
            {
                "text": "This lease automatically renews for a further 12 month term unless the {T} provides 90 days notice of non-renewal.",
                "expect": ["renewal"],
            },
            {
                "text": "Renewal shall be at the sole discretion of the {L} at a revised rent determined solely by the {L}.",
                "expect": ["renewal"],
            },
        ],
    },
}

# Boilerplate/neutral clauses used as distractors; must never flag.
NEUTRAL_CLAUSES = [
    "The {T} shall use the premises for residential purposes only.",
    "The {T} shall not sublet the premises without the prior written consent of the {L}.",
    "Utilities: the {T} pays electricity and internet, while the {L} pays for water and common area maintenance.",
    "Pets: one cat is permitted with prior written approval of the {L}.",
    "The {T} shall permit prospective tenants to view the premises during the final month of the term at reasonable hours with prior intimation.",
    "This agreement shall be governed by the laws applicable to the location of the premises.",
    "Each party has read and understood the terms of this agreement before signing.",
    "The stamp duty and registration charges of this agreement shall be shared equally by both parties.",
]

PARTY_SYNONYMS = [
    ("Landlord", "Tenant"),
    ("Lessor", "Lessee"),
    ("Licensor", "Licensee"),
    ("Owner", "Tenant"),
]

RENT_CLAUSES = [
    ("The monthly rent is {rent_usd} payable in advance, due on the 1st day of each month.", "rent_usd"),
    ("The monthly rent shall be {rent_inr} payable on or before the 5th day of each English calendar month.", "rent_inr"),
]

HEADERS = [
    "RESIDENTIAL LEASE AGREEMENT",
    "RENT AGREEMENT",
    "LEAVE AND LICENSE AGREEMENT",
]

RECITALS = [
    "This agreement is made between {landlord_name} (hereinafter the {L}) and {tenant_name} (hereinafter the {T}) for the premises at {address}.",
]

NAMES_L = ["Jane Smith", "Ramesh Kumar", "Property Holdings LLC", "Arjun Mehta", "Susan Lee"]
NAMES_T = ["Robert Chen", "Priya Sharma", "David Okafor", "Neha Verma", "Maria Garcia"]
ADDRESSES = [
    "421 Oak Street, Los Angeles, California",
    "C-14, Lajpat Nagar, New Delhi",
    "Flat 702, Sea Breeze Towers, Mumbai, Maharashtra",
    "88 Pecan Drive, Austin, Texas",
]
