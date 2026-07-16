# Fissiamo esplicitamente Debian 12 (Bookworm) per evitare rotture future
FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# 1. Installa dipendenze base e certificati
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 curl gnupg2 apt-transport-https unixodbc-dev ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# 2. Usa il repository corretto di Microsoft per Debian 12
RUN curl -fsSL https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg \
    && curl -fsSL https://packages.microsoft.com/config/debian/12/prod.list > /etc/apt/sources.list.d/mssql-release.list \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y msodbcsql18 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 3. Dipendenze Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4. Download pesi YOLO
RUN python -c "from ultralytics import YOLO; YOLO('yolov8n.pt')"

# 5. Copia del codice e permessi
COPY ./app /app

RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

CMD ["gunicorn", "main:app", "-w", "2", "-k", "uvicorn.workers.UvicornWorker", "-b", "0.0.0.0:8000", "--timeout", "120"]