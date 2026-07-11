"""PDF / text intake. pypdf and OCR deps are imported lazily so the core
analysis package has no hard dependency on them."""


def extract_pdf_text(uploaded_file):
    from pypdf import PdfReader

    text_parts = []
    uploaded_file.seek(0)
    pdf = PdfReader(uploaded_file)

    for page in pdf.pages:
        page_text = page.extract_text() or ""
        if page_text.strip():
            text_parts.append(page_text)

    text = "\n".join(text_parts)
    if text.strip():
        return text

    return extract_text_with_ocr(uploaded_file.getvalue())


def extract_text_with_ocr(pdf_bytes):
    try:
        import pytesseract
        from pdf2image import convert_from_bytes
    except ImportError:
        return ""

    try:
        images = convert_from_bytes(pdf_bytes)
        extracted = []
        for image in images:
            extracted.append(pytesseract.image_to_string(image))
        return "\n".join(extracted)
    except Exception:
        return ""
