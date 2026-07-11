# Rent Agreement Analyzer

A Streamlit website that reviews rent agreements (PDF or pasted text), extracts key terms, flags trap clauses, and produces a downloadable report — in English, Hindi, Bengali, Marathi, Telugu, or Tamil. Pure code — no external APIs or LLMs; nothing leaves your machine.

## Languages

- **Analyze in any of the 6 languages**: agreements written in Hindi/Bengali/Marathi/Telugu/Tamil are converted to analyzable English via an offline lease-domain glossary (`rent_analyzer/translate.py`).
- **Reports in any of the 6 languages**: all risk explanations, labels, and summaries are natively localized (`rent_analyzer/i18n.py`) — not machine-translated.
- **Translate tab**: any→any across all 30 language pairs. Glossary-based (legal terms precise, unknown words pass through); optionally upgrades to a local neural model if `argostranslate` is installed — still fully offline.

## Architecture

```
app.py                 Streamlit website (thin — no logic)
rent_analyzer/         analysis package
  ingest.py            PDF/OCR intake
  preprocess.py        normalization, sentence splitting, entities
  normalize.py         typed parsers: money (₹/Rs./INR/$/words), durations, rent multiples
  facts.py             key-term extraction (rent, deposit, notice, ...)
  rules.py             risk rules with actor attribution + negation handling
  translate.py         offline 6-language glossary translator (+ optional local neural)
  i18n.py              native localization of all reports/UI strings
  analyze.py           pipeline + scoring
  report.py            summary generation (localized)
testgen/               self-testing loop
  clause_bank.py       labeled safe/trap clause templates
  generator.py         synthetic agreement generator with ground truth
  evaluate.py          precision/recall harness + failure dump
tests/                 pytest suite incl. golden files and metrics gate
```

See `ROBUSTNESS_PLAN.md` for the full design and roadmap.

## Run the app

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Run the tests

```bash
pip install -r requirements-dev.txt
python -m pytest tests
```

The suite includes a **metrics gate** (`tests/test_metrics.py`): the analyzer must keep ≥99% precision and recall on generated corpora, including a held-out seed. If a change regresses detection, tests fail.

## Self-test loop

Generate labeled agreements and measure detection quality:

```bash
python -m testgen.evaluate --n 200 --seed 42 --failures 20
```

Reports per-category precision/recall and dumps every miss / false flag. The improvement workflow: run the evaluator, fix the rule or normalizer for each failure, add the failing phrasing to `testgen/clause_bank.py` as a permanent regression test, and re-run until clean.

Golden files pin full pipeline output per fixture; regenerate intentionally with:

```bash
python tools/regen_goldens.py
```

## Disclaimer

Automated document review, not legal advice. Jurisdiction thresholds in `rent_analyzer/rules.py` are simplified norms — verify against current local law.
