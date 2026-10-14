"""Extract text or fail closed; NEVER return a fabricated invoice."""
import io
from fastapi import HTTPException, status
from PIL import Image, UnidentifiedImageError


def extract_text(contents: bytes, filename: str) -> str:
    is_pdf = contents.startswith(b"%PDF-")
    is_image = contents.startswith((b"\x89PNG\r\n\x1a\n", b"\xff\xd8\xff"))
    if not (is_pdf or is_image):
        raise HTTPException(415, "Only genuine PDF, PNG and JPEG files are supported")
    try:
        import pytesseract
        from pytesseract import TesseractNotFoundError
        if is_pdf:
            from PyPDF2 import PdfReader
            reader = PdfReader(io.BytesIO(contents))
            if reader.is_encrypted or len(reader.pages) > 5:
                raise HTTPException(422, "Encrypted PDFs or PDFs over five pages are not supported")
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
            if len(text.strip()) >= 25:
                return text
            from pdf2image import convert_from_bytes
            images = convert_from_bytes(contents, dpi=180, first_page=1, last_page=len(reader.pages))
        else:
            images = [Image.open(io.BytesIO(contents))]
        text = "\n".join(pytesseract.image_to_string(img.convert("RGB")) for img in images)
        if not text.strip():
            raise HTTPException(422, "Could not read text from document; enter activity manually")
        return text
    except HTTPException:
        raise
    except (ImportError, TesseractNotFoundError):
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "OCR engine unavailable; install Tesseract and Poppler")
    except (UnidentifiedImageError, ValueError, OSError) as exc:
        raise HTTPException(422, "Document could not be processed") from exc
