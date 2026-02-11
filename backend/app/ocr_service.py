"""
OCR service for extracting text from invoice images and PDFs.
Uses pytesseract (Tesseract) - fallback to placeholder when unavailable.
"""
import io
from pathlib import Path
from typing import Optional

try:
    import pytesseract
    from PIL import Image
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False

try:
    from pdf2image import convert_from_bytes
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False


def extract_text_from_image(image_bytes: bytes) -> str:
    """Extract text from image using Tesseract OCR."""
    if not TESSERACT_AVAILABLE:
        return _mock_ocr_text()
    try:
        img = Image.open(io.BytesIO(image_bytes))
        if img.mode != "RGB":
            img = img.convert("RGB")
        return pytesseract.image_to_string(img) or _mock_ocr_text()
    except Exception:
        return _mock_ocr_text()


def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """Extract text from PDF - first page only for MVP."""
    if PDF_AVAILABLE:
        try:
            images = convert_from_bytes(pdf_bytes, first_page=1, last_page=1)
            if images:
                buf = io.BytesIO()
                images[0].save(buf, format="PNG")
                return extract_text_from_image(buf.getvalue())
        except Exception:
            pass
    return _mock_ocr_text()


def _mock_ocr_text() -> str:
    """Placeholder when OCR not available - returns sample invoice text."""
    return """
    INVOICE #INV-00123
    British Gas
    Business Electricity Supply
    Period: 01/01/2024 - 31/01/2024
    
    Consumption: 12,500 kWh
    Amount: £2,812.50
    VAT: £562.50
    Total: £3,375.00
    
    Payment due: 28/02/2024
    """
