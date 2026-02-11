# AI-Powered RegTech Platform for SME ESG Compliance

An AI-powered SaaS platform that automates ESG data collection and reporting. Uses NLP to extract data from invoices, calculates carbon emissions using **UK DEFRA conversion factors 2024**, and generates audit-ready ESG scorecards aligned with UK SRS standards.

## 🏗️ What's Included

- **Emission factors dataset** – UK Government GHG conversion factors 2024 (DEFRA/DESNZ), stored in `backend/data/emission_factors.json`
- **Official DEFRA flat file** – Downloaded to `backend/data/defra_conversion_factors_2024.xlsx`
- **Synthetic invoice data** – 100 sample invoices in `backend/data/synthetic_invoices.json` and `.csv`
- **Carbon calculation engine** – Applies emission factors, classifies transactions by category
- **NLP pipeline** – Keyword-based classification (extensible to spaCy/HuggingFace)
- **OCR service** – Tesseract for images/PDFs (falls back to mock when unavailable)
- **ESG dashboard** – Scope 1/2/3 totals, category breakdown, transaction table
- **PDF-ready report** – HTML report for browser Print → Save as PDF

## Tech Stack

| Layer    | Tech                          |
| -------- | ----------------------------- |
| Frontend | Next.js 14, React, Tailwind   |
| Backend  | Python FastAPI                |
| AI/NLP   | Keyword classification        |
| OCR      | pytesseract (optional)        |
| Data     | JSON + SQLite                 |

## Quick Start

### 1. Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Mac/Linux
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

### 3. Access

- **Frontend:** http://localhost:3000
- **Backend API:** http://localhost:8000
- **API Docs:** http://localhost:8000/docs

## Data & Scripts

- `backend/scripts/generate_synthetic_invoices.py` – Generate sample invoice data (already run)
- `backend/scripts/download_emission_factors.py` – Download official DEFRA Excel (already run)
- `backend/data/emission_factors.json` – Curated emission factors for the app
- `backend/data/synthetic_invoices.json` – Sample transactions for demo

## Features

- ✅ Document upload (PDF, images)
- ✅ OCR + NLP extraction (supplier, amount, category)
- ✅ Automatic carbon calculation (Scope 1, 2, 3)
- ✅ ESG dashboard & scorecard
- ✅ Exportable report (Print to PDF)
- ✅ UK SRS aligned reporting
