# Self-Check Answer Key

How to use: open the app → Analyze tab → open one of the 5 example .txt files in this
folder → copy-paste its text into the app → leave Jurisdiction on "Auto-detect" →
click Analyze. Compare what you see against the answers below. If everything matches,
the app is working correctly.

Severity colors in the app: red = Severe, orange = Moderate, yellow = Mild.

---

## Example 1 — 1_fair_lease_california.txt (a GOOD lease)

- Safety score: **100/100**, band: **Low Risk**
- Jurisdiction detected: USA — California
- Risk flags: **NONE** (green "no suspicious clauses" message)
- Key terms found: rent **$2,200** · deposit **$2,200** · notice **30 days**
- Why this matters: this lease deliberately contains words like "structural repairs",
  "arbitrator", "guests", "terminate" — in FAIR wording. A weak analyzer would
  false-alarm on them. Yours should stay silent.

## Example 2 — 2_trap_heavy_delhi.txt (worst-case landlord)

- Safety score: **0/100**, band: **High Risk**
- Jurisdiction detected: India — Delhi
- Risk flags: **10 total — 9 Severe + 1 Moderate**, covering ALL of:
  - Deposit (severe) — 10 months' rent AND never refunded
  - Late fee (severe) — ₹1,500 per day
  - Entry (severe) — landlord enters at all hours, no notice
  - Eviction (severe, appears twice) — 48-hour "any reason" eviction AND
    lock-the-premises/cut-utilities self-help eviction
  - Rights waiver (severe) — waives all tenant protections
  - Repairs (severe) — tenant pays for structural repairs
  - Complaints to authorities (severe) — banned from complaining to government
  - Dispute resolution (severe) — landlord picks the arbitrator, tenant pays
  - Guest policy (moderate) — no overnight guests without written permission
- Key terms: rent **₹30,000**; deposit shows "Not clearly found" — correct,
  because the deposit is written as "ten months' rent", not as an amount.

## Example 3 — 3_medium_risk_mumbai.txt (mostly fine, two catches)

- Safety score: **68/100**, band: **Medium Risk**
- Jurisdiction detected: India — Maharashtra
- Risk flags: **exactly 2, both Moderate — no red flags**
  - Deposit (moderate) — 60-day return window is longer than the 30-day norm
  - Renewal (moderate) — auto-renews unless you give 90 days notice (easy trap)
- Everything else (₹500 late fee with grace period, 48-hour inspection notice,
  landlord doing structural repairs) should NOT be flagged.
- Key terms: rent **₹45,000** · notice **90 days**

## Example 4 — 4_hindi_agreement.txt (written entirely in Hindi)

- Safety score: **28/100**, band: **High Risk**
- Risk flags: **3 Severe**
  - Deposit (severe) — जमानत राशि गैर-वापसी योग्य (non-refundable deposit)
  - Entry (severe) — बिना नोटिस किसी भी समय प्रवेश (entry any time, no notice)
  - Repairs (severe) — संरचनात्मक मरम्मत किरायेदार पर (structural repairs on tenant)
- Key terms: rent **₹18,000** · deposit **₹1,50,000**
- Bonus check: switch "Report language" in the sidebar to हिन्दी — the whole
  report should switch to Hindi.

## Example 5 — 5_subtle_legalese_texas.txt (traps hidden in lawyer-speak)

- Safety score: **0/100**, band: **High Risk**
- Jurisdiction detected: USA — Texas
- Risk flags: **5 Severe**
  - Eviction (severe) — "quit and deliver up vacant possession within forty eight
    (48) hours at the absolute discretion of the Lessor" (no trigger words like
    "evict" — caught from the legalese itself, including the number written in words)
  - Rights waiver (severe) — jury trial + counterclaim waived
  - Penalty (severe) — "$25 per nail hole" deducted from deposit
  - Rent increase (severe) — "revised as per market rate at any time"
  - Dispute resolution (severe) — flows from the jury-trial waiver
- The fair clauses (30-day deposit return, reasonable entry notice, landlord
  maintains the roof) should NOT be flagged.
- Key terms: rent **$1,750** · deposit **$1,750** · notice **30 days**

---

If any example gives a different result than listed here, something is broken —
tell Claude which example and what you saw instead.
