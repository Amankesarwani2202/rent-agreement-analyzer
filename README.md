# Rent Agreement Analyzer

A Streamlit app for reviewing rent agreement PDFs and pasted text. It extracts key terms, highlights risky clauses, and produces a downloadable summary.

## Features
- Upload a rent agreement PDF
- Paste agreement text directly
- Extract key terms such as rent, deposit, lease term, notice period, and pet policy
- Highlight common risk clauses such as automatic renewal, termination, and deposit deductions using a jurisdiction-aware rule engine
- **ML risk scanner**: a local scikit-learn (TF-IDF + Logistic Regression) model, trained in-process on bundled examples, that flags risky/one-sided clauses phrased differently from the fixed keyword rules
- **Neural translation**: local, offline machine translation (Argos Translate) between English and Hindi, with an instant dictionary-based fallback
- Download a plain-text analysis summary

No external AI API is used anywhere in this app — everything runs locally with open-source Python/ML libraries (spaCy, scikit-learn, Argos Translate).

### Translation engines
- **Neural (default)**: uses [Argos Translate](https://github.com/argosopentech/argos-translate), an offline neural MT library. The first translation for a language pair downloads a small open model file once; after that, every translation runs entirely on-device with no network calls.
- **Dictionary**: an instant, fully offline word-substitution translator for common lease vocabulary. Used automatically as a fallback if the neural model can't be downloaded (e.g. no internet at deploy time).

### ML risk scanner
In addition to the deterministic keyword/jurisdiction rules, a small logistic regression classifier (trained at startup on ~120 bundled example clauses) scores every sentence in the agreement and surfaces ones that read as risky or one-sided but don't match the fixed keyword list — useful for catching paraphrased language. Treat it as a second opinion, not a verdict.

## Streamlit Cloud deployment
1. Push this repository to GitHub.
2. Open Streamlit Cloud and create a new app from the repository.
3. Set the main file to app.py.
4. Streamlit Cloud will install dependencies from requirements.txt automatically.

## Local development
```bash
python -m pip install -r requirements.txt
streamlit run app.py
```

## Notes
- The app is designed to work in Streamlit Cloud without ngrok or Colab-specific setup.
- For best text extraction, use text-based PDFs rather than scanned image-only PDFs.
- All analysis (extraction, risk detection, translation) runs locally in the app process — no data is sent to any third-party AI API.
