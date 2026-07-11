# Rent Agreement Analyzer — Robustness Plan

Goal: pure-code (no external API/LLM) analyzer that reliably catches trap clauses in rent agreements, extracts key terms accurately, and can prove its own accuracy via a built-in synthetic-agreement test loop.

---

## 1. Why the current code breaks

These are concrete failure modes in `app.py` today. Each one maps to a workstream below.

**1.1 Substring keyword matching, no context.**
`if "eviction" in text` flags *"Eviction will follow due legal process with 60 days notice"* — a perfectly fair clause. Conversely, *"Lessor may re-enter and take possession forthwith"* is an eviction trap with zero matching keywords → missed.

**1.2 No negation or party attribution.**
*"The landlord shall NOT enter without 24 hours notice"* triggers the entry flag because "without notice" appears. The code never determines who the obligation binds or whether the sentence permits or prohibits the behavior.

**1.3 Brittle numeric extraction.**
Only digit+symbol formats are caught. Misses: "rupees fifty thousand", "Rs. 50,000/-", "INR 50000", "two months' rent as deposit", "sixty (60) days", "1.5 lakh", "one-half of one month's rent". Any agreement written in standard Indian legal drafting style slips through the deposit/rent/notice extraction entirely.

**1.4 Sentence-level analysis loses clause structure.**
Legal drafting uses numbered clauses, sub-clauses (a)/(b)/(i)/(ii), provisos, and semicolon lists. Splitting on `.!?` fragments them; a trap buried in sub-clause (iii) of a 400-word section is analyzed as noise. The `len(sentence) > 25` filter silently drops short but critical sentences ("Deposit is non-refundable.").

**1.5 Jurisdiction inference is dangerously loose.**
`"ca" in lowered` matches "in **ca**se of", "appli**ca**ble". "dl", "tx", "mh" similarly. Wrong jurisdiction → wrong thresholds → wrong verdicts.

**1.6 Rule conditions are shallow and hardcoded.**
`build_risk_flag` checks a handful of literal phrases ("for any reason", "48 hours", "per nail"). A landlord writing "tenant waives any claim to interest on deposit and agrees rent may be revised at lessor's sole discretion" trips nothing. Legal knowledge is welded into Python `if` chains — hard to audit, extend, or test.

**1.7 No cross-clause reasoning.**
Traps often live in the *combination*: deposit = 10 months' rent (needs deposit AND rent, compared); notice period 1 month for tenant but 1 week for landlord (asymmetry); lock-in of 11 months + "landlord may terminate anytime" (contradiction). Nothing in the code compares two extracted facts.

**1.8 Fake translation.**
The Hindi "translation" is a 12-word replace map — it produces garbage that then flows into English regexes. Either handle Hindi properly or detect and clearly decline.

**1.9 Arbitrary scoring, duplicated pipelines.**
Two parallel risk systems exist (`RISK_RULES`/`detect_red_flags` and `classify_clauses`) with different scores; `main()` re-runs extraction the app already did inside `analyze_agreement`. Points (8/16/24) have no calibration and no cap per category, so three mild flags outrank one catastrophic clause.

**1.10 Zero tests.** No way to know whether any change makes detection better or worse. This is the root cause of "not robust" — fixing it is Section 5.

---

## 2. Target architecture

Replace the flat keyword scan with a staged pipeline. Each stage has one job, typed inputs/outputs, and its own tests.

```
PDF/text ──> Ingestion ──> Normalization ──> Structure Parser ──> Clause Classifier
                                                                        │
Report <── Scorer <── Consistency Checker <── Rule Engine <── Fact Extractor
```

Proposed module layout (extract logic out of the Streamlit file):

```
rent_analyzer/
  ingest.py          # PDF/OCR/text intake, encoding cleanup
  normalize.py       # numbers-in-words, currency, durations, dates
  structure.py       # clause/section segmentation, hierarchy
  classify.py        # clause -> category tagging
  facts.py           # typed fact extraction (rent, deposit, notices...)
  rules/
    engine.py        # generic rule evaluator
    base.yaml        # jurisdiction-independent rules
    us_ca.yaml, in_dl.yaml, in_mh.yaml, ...
  consistency.py     # cross-clause checks
  scoring.py         # severity -> score, confidence
  report.py          # summary generation
testgen/
  generator.py       # synthetic agreement generator (Section 5)
  clause_bank.yaml   # parameterized trap/safe clause templates
  perturb.py         # paraphrase/noise/format perturbations
  evaluate.py        # precision/recall harness + failure reports
tests/
  test_*.py          # unit + golden-file regression tests
app.py               # thin Streamlit UI over rent_analyzer
```

---

## 3. Workstreams in detail

### 3.1 Normalization layer (`normalize.py`)

One canonical representation for every quantity before any rule runs.

- **Money**: parse `₹`, `Rs.`, `Rs`, `INR`, `$`, `USD`, `/-` suffix, Indian digit grouping (1,50,000), words ("fifty thousand", "one lakh twenty thousand", "1.5 lakhs"), and rent-relative amounts ("two months' rent" → `Money(multiple_of_rent=2)`).
- **Durations**: "60 days", "sixty (60) days", "two months", "one calendar month", "a fortnight" → `Duration(days=…)`. Handle the "(60)" legal convention: prefer the parenthesized numeral, flag if words and numeral disagree (itself a classic trap/typo).
- **Dates**: `1st April 2026`, `01/04/2026` (day-first for IN, month-first for US — resolve using jurisdiction), `April 1, 2026`.
- **Percentages**: "10% per annum", "ten percent increase annually".
- **Ordinals** for due dates: "fifth day of each English calendar month".

Every parser returns a value + source span + confidence. ~50 unit tests each, written first.

### 3.2 Structure parser (`structure.py`)

- Detect numbered/lettered headings (`1.`, `1.1`, `(a)`, `(iv)`, `ARTICLE V`, ALL-CAPS headings) and build a clause tree.
- Split long clauses on provisos ("provided that", "notwithstanding", "subject to") and semicolon lists into analyzable sub-units **while retaining parent context** (a sub-clause knows its section is "TERMINATION").
- Repair PDF artifacts: hyphenated line breaks, headers/footers repeated per page, column bleed, OCR confusions (l/1, O/0 inside numbers).
- No minimum-length filter; short sentences are often the traps.

### 3.3 Clause classifier (`classify.py`)

Tag each clause with zero or more categories: `rent`, `deposit`, `termination`, `entry`, `repairs`, `renewal`, `dispute`, `fees`, `subletting`, `guests`, `utilities`, `lock_in`, `indemnity`, `waiver`, `alterations`, `insurance`.

- **Stage 1 — weighted lexicons**: per category, a curated list of phrases and regexes with weights, including legalese synonyms ("lessor/lessee", "demised premises", "quit and deliver up", "re-enter", "distrain", "vacant possession", "licence fee" for Mumbai leave-and-license). Score above threshold → tag. This replaces bare `in` checks and is data (YAML), not code.
- **Stage 2 (optional, still pure-code)**: a TF-IDF + logistic-regression classifier (scikit-learn) trained on the synthetic corpus from Section 5, used to catch clauses the lexicons miss. Ships as a pickled model, runs offline, no API.
- A clause with a category tag but **no extractable facts and no rule match** is surfaced as "needs human review" instead of silently passing.

### 3.4 Negation, modality, and party attribution

For each clause, before any rule fires, determine:

- **Modality**: obligation (shall/must), permission (may/is entitled), prohibition (shall not/may not/is prohibited from), waiver (waives/relinquishes/forfeits).
- **Actor**: landlord/lessor/owner/licensor vs tenant/lessee/licensee (plus resolved party names from the recitals — "hereinafter referred to as the LESSOR").
- **Negation scope**: pattern-based first ("shall not X without Y" = conditional permission, usually fine; "may X without Y" = trap); use spaCy dependency parse as a tiebreaker, with the pattern rules as the authority since parses on legalese are unreliable.
- **Exceptions**: "except in case of emergency" attached to entry clauses is normal and must suppress the flag.

Output per clause: `(actor, modality, action_category, conditions, negated)`. Rules then match on this structure, killing the "landlord shall NOT enter" false-positive class entirely.

### 3.5 Declarative rule engine (`rules/`)

Move all legal knowledge to YAML. A rule = category + structured condition over extracted facts + severity + rationale + law reference. Example:

```yaml
- id: deposit_excessive
  category: deposit
  when: deposit.months_of_rent > jurisdiction.deposit_max_months
  severity: severe
  rationale: "Deposit of {deposit.months_of_rent} months' rent exceeds the {jurisdiction.deposit_max_months}-month norm for {jurisdiction.name}."
  reference: jurisdiction.deposit_reference

- id: notice_asymmetry
  category: termination
  when: tenant.notice_days >= 2 * landlord.notice_days
  severity: moderate
  rationale: "Tenant must give {tenant.notice_days} days notice but landlord only {landlord.notice_days} — one-sided."
```

Benefits: auditable, testable rule-by-rule, extensible per jurisdiction without touching the engine, and each fired rule carries its evidence span. Jurisdiction is **user-selected in the UI** (dropdown, required); auto-inference only as a suggestion, and only from strong signals (statute citations, full state names, PIN/ZIP codes) — never 2-letter substrings.

### 3.6 Trap clause library

The heart of robustness. Enumerate known traps as first-class rule targets, each with detection patterns AND fair-variant counter-patterns (so fair clauses don't flag). Initial catalog:

**Money traps**: non-refundable deposit; deposit > jurisdiction cap (incl. expressed as months of rent); deposit deductions for "normal wear and tear"; forfeiture of full deposit on early exit; interest on deposit waived where law requires it; late fee excessive/per-day/uncapped/no grace period; fee stacking (cleaning + painting + admin + move-out fees); rent payable in cash only / no receipts; broker/registration/TDS costs shifted entirely to tenant; post-dated cheques for the full term; liquidated damages disguised as "penalty".

**Control traps**: entry without notice / "at any time" / master key retention; unusually restrictive guest/visitor limits; prohibition on overnight guests; curfew clauses; restrictions on food habits or religious practice presented as binding; blanket alteration bans down to nails/fixtures with per-item fines.

**Termination traps**: landlord terminates "at any time"/"for any reason"/"at sole discretion"; asymmetric notice periods; lock-in requiring full remaining rent on early exit; self-help eviction (lockout, utility disconnection, belongings removal); eviction notice below legal minimum; automatic renewal with penalty to decline; renewal only at landlord's "revised rent at sole discretion".

**Rights-waiver traps**: waiver of habitability/essential services; waiver of statutory notice; waiver of right to contact authorities or complain to rent court (retaliation clauses); jury waiver / one-sided arbitration (landlord picks arbitrator, tenant pays costs); venue fixed far from the premises; one-way attorney-fee shifting; confession of judgment; blanket indemnity of landlord including landlord's own negligence.

**Maintenance traps**: structural/major repairs shifted to tenant; "as-is" acceptance waiving defect claims; tenant maintains "in the same condition" (impossible standard); landlord repair obligations "at landlord's convenience" with no timeline.

**Ambiguity traps** (flag as review-needed, not illegal): "reasonable" charges undefined; charges "as determined by landlord"; rent revision "as per market rate"; obligations "and such other conditions as landlord may impose".

Each entry gets ≥5 phrasing variants in the clause bank (Section 5) so detection is validated against realistic wording, not the one phrase the rule author imagined.

### 3.7 Cross-clause consistency (`consistency.py`)

- Deposit vs rent ratio (needs both facts).
- Tenant vs landlord notice asymmetry.
- Lock-in clause vs landlord's termination-anytime clause (contradiction → severe).
- Stated lease dates vs stated term ("commencing 1 June 2026 for 11 months, ending 30 April 2026" — impossible).
- Total move-in cost (deposit + advance + fees) as a rent multiple.
- Duplicate/conflicting clauses (two different late fees) — flag the conflict itself.
- Words-vs-numerals mismatches ("sixty (30) days").

### 3.8 Scoring & reporting (`scoring.py`, `report.py`)

- One scoring path (delete the `RISK_RULES` duplicate).
- Per-category caps so five mild fee quibbles can't outweigh one self-help-eviction clause; any `severe` in rights-waiver/termination floors the band at High.
- Every flag carries: rule id, severity, confidence, exact quoted evidence with clause number, plain-language explanation, and "what a fair version looks like".
- Explicit **coverage report**: which of the ~16 categories were found, which were absent ("this agreement is silent on deposit return timeline — that itself is a risk"). Silence-as-risk is a major gap in the current tool.
- Keep the disclaimer; add per-flag confidence so users know pattern-match certainty.

---

## 4. Hindi / multilingual

The current replace-map must go. Pragmatic pure-code path:

1. Detect Devanagari; if >20% of chars, route to Hindi mode.
2. Hindi mode v1: honest message that Hindi analysis is limited + run a *Hindi-native* lexicon (deposit = जमानत/अग्रिम, notice = सूचना, etc.) for key-term extraction only — no fake translation into the English pipeline.
3. Optional later: offline translation via a local model (e.g., argos-translate) — still no API — gated behind an extra install.

---

## 5. Self-testing loop: synthetic agreement generator + evaluator

This is the mechanism that makes robustness measurable and improvable, exactly as you described: generate agreements with known traps → run the analyzer → diff expected vs detected → fix what's missed → repeat.

### 5.1 Clause bank (`testgen/clause_bank.yaml`)

For every category: multiple **safe** templates and multiple **trap** templates, parameterized:

```yaml
deposit:
  safe:
    - "The Tenant shall pay a refundable security deposit of {money}, returnable within {days:15-30} days of vacating, subject to deductions for damage beyond normal wear and tear."
  trap:
    - id: deposit_nonrefundable
      text: "The Lessee shall pay {money} as a non-refundable security deposit."
      expect: [deposit_nonrefundable]
    - id: deposit_excessive
      text: "The Licensee shall deposit an amount equivalent to {n:6-12} months' licence fee as interest-free refundable deposit."
      expect: [deposit_excessive]
      params: {jurisdiction_dependent: true}
```

Every template declares `expect`: the rule ids that MUST fire (and implicitly, all others must NOT). Safe templates declare `expect: []` — they are the false-positive tests, equally important.

### 5.2 Document generator (`testgen/generator.py`)

- Assemble full agreements: recitals (party names, addresses from a name/place pool), numbered clauses drawn per category (each independently safe or trap by a seeded RNG), witness block, annexures.
- Emit alongside each document a **ground-truth JSON**: expected rule ids, expected key terms (rent=₹X, deposit=Y months, notice=Z days, dates), jurisdiction.
- Skeleton styles: Indian leave-and-license, Indian 11-month rent agreement, US residential lease — different structure conventions stress the structure parser.

### 5.3 Perturbation engine (`testgen/perturb.py`)

Applied to generated docs to simulate the real world:

- **Lexical**: synonym swaps (landlord↔lessor↔licensor↔owner), legalese inflation ("shall quit and deliver up vacant possession").
- **Numeric format**: digits ↔ words ↔ "sixty (60)", ₹↔Rs.↔INR, Indian grouping, "/-".
- **Structural**: renumber clauses, merge traps into long multi-part sections, bury a trap in sub-clause (iv), move it into an annexure.
- **Noise**: OCR simulation (l↔1, O↔0, dropped spaces, hyphenated line breaks, repeated page headers), whitespace mangling.
- **Order/distraction**: shuffle clause order, insert benign boilerplate padding.

Each perturbation preserves the ground-truth labels, so one clause bank yields thousands of labeled variants.

### 5.4 Evaluation harness (`testgen/evaluate.py`)

```
python -m testgen.evaluate --n 500 --seed 42 --jurisdiction IN-DL
```

- Runs the analyzer over N generated docs; compares fired rules vs `expect`.
- Reports per rule id: **precision, recall, F1**; per key term: extraction accuracy (exact + tolerance match); overall false-positive rate on safe clauses.
- **Failure dump**: for every miss/false-fire, writes the clause text, expected vs actual, and the pipeline stage where it diverged (not classified? classified but fact not extracted? fact extracted but rule condition failed?). This stage attribution is what makes the fix loop fast.
- Tracks metrics per perturbation type, so you can see e.g. "recall drops 30% under OCR noise" and know where to invest.

### 5.5 The improvement loop

1. Run harness → read failure dump.
2. Fix = usually add lexicon phrases, a normalizer case, or a rule condition (data changes, rarely code).
3. Add the failing clause verbatim to the clause bank so it becomes a permanent regression test.
4. Re-run; commit only if no metric regressed (enforced by a pytest gate: `test_metrics.py` asserts per-rule recall ≥ last committed baseline stored in `baselines.json`).

Guard against overfitting to the generator: keep a **held-out template set** never used during fixing, evaluated only at milestones; and hand-write 10–15 realistic full agreements (including real-world-style ones you collect) as a golden set with manually verified labels.

### 5.6 Optional: generator → classifier training

The labeled corpus doubles as training data for the Stage-2 TF-IDF classifier (3.3), giving ML-level generalization with zero external calls.

---

## 6. Test infrastructure

- `pytest` suite: unit tests per normalizer/parser (fast, hundreds), golden-file tests (full doc → full expected report JSON), metric-baseline gate from 5.5.
- Property tests (hypothesis) for normalizers: any generated money string round-trips to the right value.
- CI (GitHub Actions): run unit + a 200-doc seeded evaluation on every push; fail on baseline regression.
- Streamlit app becomes a thin UI; all logic importable and testable headlessly.

---

## 7. Phased roadmap

**Phase 0 — Foundation (do first, ~small)**
Extract logic from `app.py` into `rent_analyzer/` package; delete the duplicate `RISK_RULES` pipeline; add pytest scaffolding; pin the current behavior with a few golden files so refactors are safe.
*Done when: app works identically, logic importable, CI green.*

**Phase 1 — Normalization + structure**
`normalize.py` (money/duration/date/percent incl. words + Indian formats) and `structure.py` (clause tree, proviso splitting, PDF cleanup). Highest ROI: most current misses are extraction misses.
*Done when: normalizer unit tests pass ≥99%; key-term extraction accuracy on a 100-doc generated set ≥95% (vs. current baseline measured in Phase 0).*

**Phase 2 — Test generator + harness (unlocks everything else)**
Clause bank with ~10 categories × (3 safe + 5 trap variants), generator, perturbations, evaluation with failure dump, baseline gate.
*Done when: `evaluate` runs end-to-end and produces per-rule P/R and stage-attributed failures.*

**Phase 3 — Rule engine + trap library**
YAML rule engine; port existing rules; implement the full Section 3.6 catalog; negation/modality/actor layer; jurisdiction dropdown in UI.
*Done when: recall ≥90% and precision ≥90% per trap category on the generated set including perturbations; safe-clause false-positive rate <5%.*

**Phase 4 — Consistency + coverage + reporting**
Cross-clause checks, silence-as-risk coverage report, evidence-quoting report with "fair version" suggestions, calibrated scoring.
*Done when: consistency traps (asymmetry, lock-in contradiction, ratio) detected at ≥90% recall; report shows evidence spans for every flag.*

**Phase 5 — Hardening**
Held-out template evaluation, hand-labeled realistic golden set, OCR-noise robustness push, optional TF-IDF classifier, Hindi-native lexicon mode.
*Done when: held-out F1 within 5 points of training-set F1 (i.e., not overfit to the generator).*

---

## 8. Non-goals / principles

- No external APIs or hosted LLMs anywhere in the pipeline (per requirement).
- Not legal advice — keep disclaimers; jurisdiction thresholds must cite their source and are user-verifiable in the YAML.
- Prefer data changes (lexicons, rules, templates) over code changes when fixing detection gaps — that's what keeps the loop fast and the engine stable.
- Every detection claim must be backed by a quoted evidence span; if the tool can't point to text, it doesn't flag.
