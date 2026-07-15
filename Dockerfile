FROM python:3.11-slim

# Variabili d'ambiente per Python
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Installa librerie di sistema essenziali per OpenCV e calcolo matriciale
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

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