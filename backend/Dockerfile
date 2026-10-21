FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates tesseract-ocr poppler-utils && rm -rf /var/lib/apt/lists/*
WORKDIR /srv/regtech
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./
RUN useradd --system --uid 10001 --home-dir /srv/regtech --shell /usr/sbin/nologin regtech && chown -R regtech:regtech /srv/regtech
USER regtech
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
