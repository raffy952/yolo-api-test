# 🎯 YOLOv8 Vision API - Production Ready

Un microservizio completo e pronto per la produzione per la rilevazione di persone (Person Detection) in tempo reale. 
Il sistema utilizza **YOLOv8** per l'inferenza, **FastAPI** per l'esposizione degli endpoint, **Nginx** come reverse proxy e salva i log delle predizioni su **Microsoft SQL Server**. L'intera infrastruttura è containerizzata con **Docker** e rilasciata tramite una pipeline **CI/CD su GitHub Actions**.

## 🏗️ Architettura del Sistema

- **Nginx (Reverse Proxy):** Gestisce il traffico in ingresso sulla porta 80, protegge l'API interna, estende i timeout per l'inferenza e accetta payload di grandi dimensioni (fino a 20MB).
- **FastAPI:** L'interfaccia web asincrona. Riceve le immagini, le decodifica direttamente in RAM (senza I/O su disco) e le passa al modello.
- **YOLOv8 (Ultralytics):** Modello AI (versione `nano` per inferenza CPU) pre-caricato in memoria all'avvio del container per azzerare i tempi di caricamento (Cold Start).
- **SQL Server:** Database relazionale. Attraverso SQLAlchemy e i driver nativi Microsoft (ODBC 18), salva il numero di persone rilevate, i timestamp e le coordinate JSON delle bounding box.
- **Prometheus:** Raccoglie metriche tecniche real-time dall'API (richieste/sec, latenza, errori) e metriche di business (persone rilevate, richieste totali) tramite l'endpoint `/metrics` esposto da FastAPI.
- **Grafana:** Dashboard di monitoraggio pre-configurata che combina lo storico completo da SQL Server con le metriche real-time da Prometheus.

---

## 🚀 Funzionalità Principali

- **Zero-Downtime Deploy:** Immagini Docker pre-compilate tramite CI/CD e caricate su GitHub Container Registry (GHCR).
- **Auto-Creazione Database:** L'API verifica l'esistenza del database target su SQL Server e, se assente, lo crea automaticamente all'avvio.
- **Ottimizzazione Docker Multi-stage:** Pesi del modello scaricati durante la fase di build. L'utente all'interno del container è *non-root* per massimizzare la sicurezza.
- **Elaborazione In-Memory:** Utilizzo di `numpy` e `cv2.imdecode` per elaborare i byte dell'immagine senza scrivere file temporanei.

---

## ⚙️ Prerequisiti

Per eseguire questo progetto in locale o su un server, sono necessari:
- **Docker** e **Docker Compose** (su Windows si consiglia Docker Desktop con backend **WSL2**).
- **SQL Server** (es. Express Edition) accessibile dalla rete.
- Un account GitHub (per scaricare l'immagine dal registry tramite PAT - Personal Access Token).

> **⚠️ Importante per utenti Windows:** 
> Assicurati che i file `Dockerfile` e `nginx/nginx.conf` siano salvati con terminatori di riga **LF (Line Feed)** e non CRLF, altrimenti i container Linux andranno in errore.

---

## 🛠️ Configurazione e Avvio

### 1. Configurazione del Database
Se utilizzi SQL Server su Windows locale (Host), assicurati di aver **abilitato il protocollo TCP/IP** e impostato la porta `1433` dal *SQL Server Configuration Manager*. L'Autenticazione Mista (SQL Server Authentication) deve essere attiva.

Nel file `docker-compose.yml`, aggiorna la variabile d'ambiente `DB_CONNECTION_STRING`. 
Se il DB è sull'host, utilizza `host.docker.internal`:
```text
DB_CONNECTION_STRING=mssql+pyodbc://<UTENTE>:<PASSWORD>@host.docker.internal:1433/YoloVisionDB?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes
```

### 2. Autenticazione Docker (GitHub Container Registry)
Per scaricare l'immagine compilata dalla tua pipeline, devi fare il login con Docker usando il tuo username GitHub e un **Personal Access Token (classic)** con i permessi `read:packages`:
```bash
docker login ghcr.io -u <IL_TUO_USERNAME>
# Incolla il token quando richiede la password
```
### 3. Deploy in Produzione / Locale
Apri il terminale (su Linux o WSL) nella cartella contenente il `docker-compose.yml` ed esegui:
```bash
# Scarica l'ultima immagine compilata dalla CI/CD
docker compose pull

# Avvia l'infrastruttura in background
docker compose up -d
```

## 📡 Utilizzo dell'API
Test di Salute::
```bash
curl http://localhost/health
```

Inferenza (Person Detection):
```bash
curl.exe -X POST "http://localhost/predict/person" -H "accept: application/json" -H "Content-Type: multipart/form-data" -F "file=@test/test.jpg"
```
Risposta di successo:
```bash
{
  "log_id": 1,
  "persons_detected": 1,
  "detections": [
    {
      "bbox": [5, 28, 397, 670],
      "confidence": 0.87
    }
  ]
}
```

---

## 📊 Dashboard di Monitoraggio (Grafana)

Il progetto include uno stack di monitoraggio pronto all'uso con **Prometheus** e **Grafana**, avviato automaticamente insieme agli altri servizi con `docker compose up -d`.

### Accesso alla Dashboard

1. Apri il browser su `http://localhost/grafana/` (o `http://<IP_SERVER>/grafana/` se su un server remoto). Grafana passa attraverso Nginx sulla porta 80, insieme all'API — non serve aprire porte aggiuntive sul firewall.
2. Accedi con le credenziali di default:
   - **Utente:** `admin`
   - **Password:** `admin`
   
   > ⚠️ Cambia subito la password al primo accesso, oppure impostala in modo sicuro tramite le variabili `GF_SECURITY_ADMIN_USER` / `GF_SECURITY_ADMIN_PASSWORD` nel `docker-compose.yaml`.
3. Nel menu laterale vai su **Dashboards** → troverai la dashboard **"YOLO Vision API - Monitoraggio"** già pronta.

### Cosa mostra la dashboard

- **Persone rilevate nel tempo:** andamento storico completo, letto direttamente dalla tabella `yolo_predictions` su SQL Server.
- **Totale richieste e persone rilevate (cumulativo):** contatori real-time.
- **Richieste al minuto / tasso di errore / latenza p95:** salute tecnica dell'API, utile per capire se il servizio sta reggendo il carico.
- **Distribuzione persone per richiesta:** istogramma di quante persone vengono rilevate mediamente per foto.

### Note tecniche

- Prometheus raccoglie le metriche dall'endpoint `http://yolo-api:8000/metrics`, esposto automaticamente da FastAPI grazie a `prometheus-fastapi-instrumentator`.
- I dati di Prometheus sono conservati per 30 giorni (configurabile in `docker-compose.yaml` con `--storage.tsdb.retention.time`); per lo storico a lungo termine fai riferimento a SQL Server, che non ha scadenza.
- Le credenziali del datasource SQL Server in `grafana/provisioning/datasources/datasources.yml` devono coincidere con quelle usate in `DB_CONNECTION_STRING`: aggiornale insieme se le cambi.
- Grafana non è più raggiungibile direttamente sulla porta 3000: il traffico passa esclusivamente da Nginx (`/grafana/`), riducendo la superficie esposta all'esterno. Prometheus resta accessibile solo dalla rete interna Docker, non esiste alcuna porta pubblica.