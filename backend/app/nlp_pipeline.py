"""
NLP pipeline for classifying transactions and extracting ESG-relevant data.
Uses keyword matching (lightweight) with optional spaCy for NER.
"""
import re
from typing import Optional
from .carbon_engine import CarbonEngine


class NLPPipeline:
    def __init__(self, carbon_engine: CarbonEngine):
        self.engine = carbon_engine

    def extract_from_text(self, text: str) -> dict:
        """Extract structured data from raw invoice text."""
        text_lower = text.lower()
        result = {
            "supplier": self._extract_supplier(text_lower),
            "amount": self._extract_amount(text),
            "date": self._extract_date(text),
            "description": self._extract_description(text),
            "category": self.engine.classify_from_text(text),
        }
        return result

    def _extract_supplier(self, text: str) -> Optional[str]:
        # Common supplier patterns
        suppliers = [
            "edf energy", "british gas", "octopus energy", "shell energy",
            "bp fuel", "shell fuel", "esso", "national rail", "tfl",
            "british airways", "easyjet", "ryanair", "premier inn",
            "travelodge", "dhl", "dpd", "ups", "fedex", "staples",
            "viking direct", "dell", "hp", "thames water", "biffa",
        ]
        for s in suppliers:
            if s in text:
                return s.title()
        return None

    def _extract_amount(self, text: str) -> Optional[float]:
        # £1,234.56 or GBP 1234.56 or Total: 1234.56
        patterns = [
            r"£\s*([\d,]+\.?\d*)",
            r"gbp\s*([\d,]+\.?\d*)",
            r"total[:\s]+([\d,]+\.?\d*)",
            r"amount[:\s]+([\d,]+\.?\d*)",
            r"([\d,]+\.\d{2})\s*(?:gbp|£)",
        ]
        for p in patterns:
            m = re.search(p, text, re.I)
            if m:
                try:
                    return float(m.group(1).replace(",", ""))
                except ValueError:
                    continue
        return None

    def _extract_date(self, text: str) -> Optional[str]:
        # DD/MM/YYYY, DD-MM-YYYY, YYYY-MM-DD
        patterns = [
            r"(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})",
            r"(\d{4})[/\-](\d{1,2})[/\-](\d{1,2})",
        ]
        for p in patterns:
            m = re.search(p, text)
            if m:
                g = m.groups()
                if len(g[0]) == 4:  # YYYY first
                    return f"{g[0]}-{g[1].zfill(2)}-{g[2].zfill(2)}"
                return f"{g[2]}-{g[1].zfill(2)}-{g[0].zfill(2)}"
        return None

    def _extract_description(self, text: str) -> str:
        # Use first non-empty line as description, or first 100 chars
        lines = [l.strip() for l in text.split("\n") if l.strip() and not re.match(r"^[\d£\s.,\-/]+$", l)]
        if lines:
            return lines[0][:200]
        return text[:200] if text else ""
