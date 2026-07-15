FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Installa le dipendenze di sistema, inclusi i tool per scaricare i driver Microsoft
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 curl gnupg2 apt-transport-https unixodbc-dev \
    && rm -rf /var/lib/apt/lists/*

# Aggiungi la repository Microsoft e installa l'ODBC Driver 18 per SQL Server
RUN curl -fsSL https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg \
    && curl -fsSL https://packages.microsoft.com/config/debian/11/prod.list > /etc/apt/sources.list.d/mssql-release.list \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y msodbcsql18 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
# ... (da qui in poi il Dockerfile rimane identico a prima: COPY requirements, pip install, ecc.)

# Gestione cache delle dipendenze Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Scarica i pesi del modello YOLO in fase di build per evitare download a runtime
RUN python -c "from ultralytics import YOLO; YOLO('yolov8n.pt')"

# Copia il codice sorgente
COPY ./app /app

# Sicurezza: crea un utente non-root e dagli i permessi sulla cartella
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Gunicorn con worker Uvicorn. Nota: per modelli CV pesanti su CPU, 
# troppi worker si ostacolano a vicenda. Iniziamo con 2.
CMD ["gunicorn", "main:app", "-w", "2", "-k", "uvicorn.workers.UvicornWorker", "-b", "0.0.0.0:8000", "--timeout", "120"]