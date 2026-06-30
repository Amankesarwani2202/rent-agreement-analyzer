# Rent Agreement Analyzer

A Streamlit app for reviewing rent agreement PDFs and pasted text. It extracts key terms, highlights risky clauses, and produces a downloadable summary.

## Features
- Upload a rent agreement PDF
- Paste agreement text directly
- Extract key terms such as rent, deposit, lease term, notice period, and pet policy
- Highlight common risk clauses such as automatic renewal, termination, and deposit deductions
- Download a plain-text analysis summary

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
