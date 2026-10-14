"""OCR extraction with explicit errors: NEVER fabricate invoice contents."""
import io
from fastapi import HTTPException
from PIL import Image, UnidentifiedImageError
import pytesseract
from pdf2image import convert_from_bytes

def extract_text_from_image(image_bytes: bytes) -> str:
    try:
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        content = pytesseract.image_to_string(image).strip()
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise HTTPException(422, "Invalid image or OCR engine unavailable") from exc
    except pytesseract.TesseractNotFoundError as exc:
        raise HTTPException(503, "OCR unavailable: install Tesseract on server") from exc
    if not content:
        raise HTTPException(422, "No readable text detected. Upload a clearer invoice.")
    return content

def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    try:
        images = convert_from_bytes(pdf_bytes, first_page=1, last_page=5)
    except Exception as exc:
        raise HTTPException(422, "PDF could not be converted. Check PDF and Poppler installation.") from exc
    if not images:
        raise HTTPException(422, "PDF contains no readable pages")
    pages = []
    for img in images:
        try:
            txt = pytesseract.image_to_string(img).strip()
        except pytesseract.TesseractNotFoundError as exc:
            raise HTTPException(503, "OCR unavailable: install Tesseract on server") from exc
        if txt:
            pages.append(txt)
    if not pages:
        raise HTTPException(422, "No readable text detected in PDF")
    return "\n".join(pages)
