FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    imagemagick \
    && rm -rf /var/lib/apt/lists/*

COPY src/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

WORKDIR /app

COPY src/app.py .
COPY src/templates ./templates

RUN mkdir -p uploads converted

RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 5000
CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:5000", "--workers=2", "--timeout=60"]
