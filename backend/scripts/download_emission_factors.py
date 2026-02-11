"""
Script to download official UK GHG conversion factors from GOV.UK.
The flat file is in Excel format - this script downloads it for reference.
For the app we use the JSON dataset (emission_factors.json) which contains
curated key factors. Run this to get the full official dataset.
"""
import httpx
import json
from pathlib import Path

DEFRA_FLAT_FILE_URL = "https://assets.publishing.service.gov.uk/media/6722567c10b0d582ee8c4953/ghg-conversion-factors-2024-FlatFormat_v1_1.xlsx"
OUTPUT_DIR = Path(__file__).parent.parent / "data"
OUTPUT_FILE = OUTPUT_DIR / "defra_conversion_factors_2024.xlsx"


def download_defra_factors():
    """Download the official DEFRA flat file (Excel)."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Downloading DEFRA conversion factors 2024...")
    try:
        with httpx.stream("GET", DEFRA_FLAT_FILE_URL, timeout=60) as r:
            r.raise_for_status()
            with open(OUTPUT_FILE, "wb") as f:
                for chunk in r.iter_bytes():
                    f.write(chunk)
        print(f"Saved to: {OUTPUT_FILE}")
        return True
    except Exception as e:
        print(f"Download failed: {e}")
        print("Using built-in emission_factors.json instead.")
        return False


if __name__ == "__main__":
    download_defra_factors()
