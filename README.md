# AI-Powered RegTech Platform for SME ESG Compliance

An AI-powered SaaS platform that automates ESG data collection and reporting by integrating with accounting systems. Uses NLP to extract data from invoices and receipts, calculates carbon emissions using UK DEFRA factors, and generates audit-ready ESG scorecards aligned with UK SRS standards.

## Tech Stack

- **Frontend:** Next.js 14, React, Tailwind CSS
- **Backend:** Python FastAPI
- **AI/NLP:** spaCy, HuggingFace Transformers
- **OCR:** pytesseract
- **Database:** PostgreSQL (SQLite for dev)
- **Auth:** Simple JWT (extendable to Auth0/Firebase)

## Quick Start

### 1. Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate   # Windows
pip install -r requirements.txt
python -m spacy download en_core_web_sm
uvicorn main:app --reload
```

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

### 3. Access

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

## Features

- Document upload (PDF, images)
- OCR + NLP extraction (supplier, amount, category)
- Automatic carbon calculation (Scope 1, 2, 3)
- ESG dashboard & scorecard
- Exportable PDF reports
- UK SRS aligned reporting
