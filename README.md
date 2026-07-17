# 🎯 YOLOv8 Vision API - Production Ready

Un microservizio completo e pronto per la produzione per la rilevazione di persone (Person Detection) in tempo reale.
Il sistema utilizza **YOLOv8** per l'inferenza, **FastAPI** per l'esposizione degli endpoint, **Nginx** come reverse proxy e salva i log delle predizioni su **Microsoft SQL Server**. L'intera infrastruttura è containerizzata con **Docker**, monitorata con **Prometheus** e **Grafana**, e rilasciata tramite una pipeline **CI/CD su GitHub Actions**.

## 🏗️ Architettura del Sistema

- **Nginx (Reverse Proxy):** Gestisce il traffico in ingresso sulla porta 80, protegge l'API interna, estende i timeout per l'inferenza, accetta payload di grandi dimensioni (fino a 20MB) e instrada anche il traffico verso Grafana.
- **FastAPI:** L'interfaccia web asincrona. Riceve le immagini, le decodifica direttamente in RAM (senza I/O su disco) e le passa al modello. Espone inoltre un endpoint `/metrics` per Prometheus.
- **YOLOv8 (Ultralytics):** Modello AI (versione `nano` per inferenza CPU) pre-caricato in memoria all'avvio del container per azzerare i tempi di caricamento (Cold Start).
- **SQL Server:** Database relazionale. Attraverso SQLAlchemy e i driver nativi Microsoft (ODBC 18), salva il numero di persone rilevate, i timestamp e le coordinate JSON delle bounding box.
- **Prometheus:** Raccoglie ogni 15 secondi le metriche tecniche e di business esposte dall'API (richieste, latenza, errori, persone rilevate) e le conserva per 30 giorni.
- **Grafana:** Dashboard di monitoraggio pre-configurata che combina lo storico completo da SQL Server con le metriche real-time da Prometheus.

---

## 🚀 Funzionalità Principali

- **Zero-Downtime Deploy:** Immagini Docker pre-compilate tramite CI/CD e caricate su GitHub Container Registry (GHCR).
- **Auto-Creazione Database:** L'API verifica l'esistenza del database target su SQL Server e, se assente, lo crea automaticamente all'avvio.
- **Ottimizzazione Docker Multi-stage:** Pesi del modello scaricati durante la fase di build. L'utente all'interno del container è *non-root* per massimizzare la sicurezza.
- **Elaborazione In-Memory:** Utilizzo di `numpy` e `cv2.imdecode` per elaborare i byte dell'immagine senza scrivere file temporanei.
- **Osservabilità integrata:** metriche tecniche e di business consultabili in tempo reale da Prometheus e Grafana, senza bisogno di strumenti esterni.

---

## ⚙️ Prerequisiti

Per eseguire questo progetto in locale o su un server, sono necessari:
- **Docker** e **Docker Compose** (su Windows si consiglia Docker Desktop con backend **WSL2**).
- **SQL Server** (es. Express Edition) accessibile dalla rete.
- Un account GitHub (per scaricare l'immagine dal registry tramite PAT - Personal Access Token).

> **⚠️ Importante per utenti Windows:**
> Assicurati che i file `Dockerfile`, `nginx/nginx.conf` e `prometheus/prometheus.yml` siano salvati con terminatori di riga **LF (Line Feed)** e non CRLF, altrimenti i container Linux andranno in errore.
>
> Assicurati anche che `prometheus/prometheus.yml` e i file sotto `grafana/` esistano davvero come **file**: se li scarichi/copi in modo scorretto, Windows/Docker Desktop può creare una **cartella vuota** con lo stesso nome, causando un errore di mount all'avvio (`not a directory`).

---

## 🛠️ Configurazione e Avvio

### 0. Sicurezza: credenziali, HTTPS e autenticazione

Prima di avviare i servizi, prepara tre cose:

**a) File `.env` con le tue credenziali reali, poi cifrato**
```powershell
Copy-Item .env.example .env
notepad .env   # personalizza i valori, in particolare DB_PASSWORD e GRAFANA_ADMIN_PASSWORD
```
Cifra il file con lo script incluso (ti chiede una passphrase, usa un container Docker temporaneo, non serve openssl installato):
```powershell
.\encrypt-env.ps1
```
Questo crea `.env.enc` (cifrato, sicuro da committare su Git) e puoi cancellare il `.env` in chiaro:
```powershell
Remove-Item .env
```
Ogni volta che devi avviare i servizi, decifralo al volo — questo genera anche i file individuali in `secrets/` che Docker Compose monta nei container:
```powershell
.\decrypt-env.ps1
docker compose up -d
```
`.env` e `secrets/` restano sul disco solo per il tempo necessario — sono comunque esclusi da Git in `.gitignore`.

> ⚠️ Se perdi la passphrase, non c'è modo di recuperare `.env.enc`: tienila in un posto sicuro (password manager), separata dal repository.

**Un livello in più: Docker secrets**

Le credenziali più sensibili (utente/password del DB, login admin di Grafana) non arrivano ai container come variabili d'ambiente in chiaro, ma come **file montati in sola lettura** dentro `/run/secrets/`. Questo significa che non compaiono con `docker inspect` né con `docker exec <container> env` — solo il processo applicativo dentro il container li legge, dal file. Lo trovi già configurato in `docker-compose.yaml` (blocco `secrets:` in cima al file) ed è `decrypt-env.ps1` a generare i singoli file in `secrets/` per te.

> Nota onesta: il datasource SQL Server di Grafana fa eccezione — le credenziali gli arrivano ancora come variabile d'ambiente (`$__env{DB_USER}`/`$__env{DB_PASSWORD}`), perché il provisioning YAML di Grafana non supporta la lettura da file per questo scopo specifico. È comunque protetto dagli altri livelli (file `.env` cifrato, nessun valore in chiaro nel `docker-compose.yaml`).

**b) Certificato TLS per HTTPS** (self-signed, va bene per uso locale/interno; per un dominio pubblico usa invece Let's Encrypt/Certbot)
```powershell
mkdir nginx\certs
docker run --rm -v ${PWD}/nginx/certs:/certs alpine/openssl req -x509 -nodes -days 365 -newkey rsa:2048 -keyout /certs/privkey.pem -out /certs/fullchain.pem -subj "/CN=localhost"
```
Il browser mostrerà comunque un avviso "connessione non sicura" la prima volta, perché il certificato è autofirmato: è normale, basta procedere/accettare l'eccezione.

**c) File di password per Prometheus** (basic auth)
```powershell
docker run --rm httpd:2.4-alpine htpasswd -nbB admin "LaTuaPasswordSicura" > nginx\.htpasswd
```
Sostituisci `admin` e `"LaTuaPasswordSicura"` con le credenziali che vuoi usare per accedere a Prometheus. Puoi ripetere il comando (con `>>` invece di `>`) per aggiungere altri utenti.

### 1. Configurazione del Database
Se utilizzi SQL Server su Windows locale (Host), assicurati di aver **abilitato il protocollo TCP/IP** e impostato la porta `1433` dal *SQL Server Configuration Manager*. L'Autenticazione Mista (SQL Server Authentication) deve essere attiva.

Le credenziali del database ora vivono nel file `.env` (vedi punto 0 qui sopra), non più nel `docker-compose.yaml`:
```text
DB_USER=<UTENTE>
DB_PASSWORD=<PASSWORD>
DB_SERVER=host.docker.internal
DB_PORT=1433
DB_NAME=YoloVisionDB
```
Se il DB è sull'host, `DB_SERVER` resta `host.docker.internal`.

> Se cambi queste credenziali, il datasource SQL Server di Grafana si aggiorna automaticamente: legge gli stessi valori da `.env` grazie a `GF_ENABLE_ENVIRONMENT_VARIABLE_EXPANSION`.

### 2. Autenticazione Docker (GitHub Container Registry)
Per scaricare l'immagine compilata dalla tua pipeline, devi fare il login con Docker usando il tuo username GitHub e un **Personal Access Token (classic)** con i permessi `read:packages`:
```bash
docker login ghcr.io -u <IL_TUO_USERNAME>
# Incolla il token quando richiede la password
```

### 3. Deploy in Produzione / Locale
Apri il terminale (su Linux o WSL) nella cartella contenente il `docker-compose.yaml` ed esegui:
```bash
# Scarica l'ultima immagine compilata dalla CI/CD
docker compose pull

# Avvia l'infrastruttura in background
docker compose up -d
```

Verifica che tutti i servizi siano `Up`:
```bash
docker compose ps
```

---

## 📡 Utilizzo dell'API
Test di Salute:
```bash
curl -k https://localhost/health
```

Inferenza (Person Detection):
```bash
curl.exe -k -X POST "https://localhost/predict/person" -H "accept: application/json" -H "Content-Type: multipart/form-data" -F "file=@test.jpg"
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

> Il flag `-k` dice a curl di accettare il certificato autofirmato. Se in futuro usi un certificato reale (Let's Encrypt), puoi rimuoverlo.

---

## 📊 Monitoraggio (Prometheus + Grafana)

Il progetto include uno stack di monitoraggio pronto all'uso, avviato automaticamente insieme agli altri servizi con `docker compose up -d`. Ci sono due strumenti, con scopi diversi:

| Strumento | A cosa serve | Come accederci |
|---|---|---|
| **Grafana** | Dashboard visuale, pensata per l'uso quotidiano | `https://localhost/grafana/` (tramite Nginx) |
| **Prometheus** | Query dirette sulle metriche tecniche, debug, verifica che tutto funzioni | `https://localhost/prometheus/` (tramite Nginx, richiede login) |

### 🖥️ Grafana — la dashboard pronta all'uso

**Accesso**
1. Apri `https://localhost/grafana/` (o `https://<IP_SERVER>/grafana/` su un server remoto). Passa da Nginx sulla porta 443 (HTTPS), non serve aprire altre porte sul firewall. Il browser segnalerà il certificato autofirmato: procedi/accetta l'eccezione.
2. Login con le credenziali che hai messo in `.env` (`GRAFANA_ADMIN_USER` / `GRAFANA_ADMIN_PASSWORD`).
3. Menu laterale → **Dashboards** → dashboard **"YOLO Vision API - Monitoraggio"**, già pronta e provisionata automaticamente.

**Cosa puoi vedere e fare**

- **Persone rilevate nel tempo** — grafico storico completo, letto direttamente dalla tabella `yolo_predictions` su SQL Server. Puoi filtrare per intervallo di date con il selettore in alto a destra (es. ultime 24h, ultima settimana, range custom).
- **Totale richieste elaborate** e **totale persone rilevate (cumulativo)** — contatori aggiornati in tempo reale.
- **Richieste al minuto** — quanto traffico sta ricevendo l'API in questo momento.
- **Tasso di errore (%)** — percentuale di richieste finite in errore (HTTP 5xx); utile per accorgersi subito se qualcosa si è rotto.
- **Latenza p95 dell'inferenza** — tempo di risposta che il 95% delle richieste rispetta; indicatore chiave delle prestazioni percepite dagli utenti dell'API.
- **Distribuzione persone per richiesta** — istogramma di quante persone vengono tipicamente rilevate per foto, utile per capire i pattern di utilizzo.
- **Esplorazione libera** — da qualunque pannello puoi cliccare sul titolo → **Edit** per modificare la query (SQL o PromQL), cambiare il tipo di grafico, o duplicare il pannello per crearne uno nuovo.
- **Nuovi pannelli/dashboard** — puoi creare dashboard aggiuntive da zero (icona "+" nel menu laterale), scegliendo come sorgente dati **Prometheus** (metriche tecniche/real-time) o **SQL Server - YoloVisionDB** (storico, query SQL libere sulla tabella `yolo_predictions`).

### 🔍 Prometheus — query dirette e debug

**Accesso:** `https://localhost/prometheus/` — ti verrà chiesto un login (le credenziali che hai scelto generando `nginx/.htpasswd` al punto 0). Il browser segnalerà il certificato autofirmato: procedi/accetta l'eccezione.

Pagine più utili:

- **`/targets`** (Status → Target health) — mostra se Prometheus riesce a raggiungere l'endpoint `/metrics` dell'API. Se `yolo-api` è **UP**, tutto funziona; se è **DOWN**, qui trovi anche l'errore esatto (es. `404 Not Found` di solito significa che l'immagine in esecuzione è una versione vecchia senza l'endpoint `/metrics`).
- **`/graph`** (Query) — permette di scrivere query **PromQL** e vederne il risultato in tabella o grafico. Query utili da provare:

  | Query PromQL | Cosa restituisce |
  |---|---|
  | `up{job="yolo-api"}` | `1` se l'API è raggiungibile, `0` se è giù |
  | `http_requests_total` | Contatore totale delle richieste HTTP ricevute |
  | `persons_detected_total` | Totale cumulativo di persone rilevate da tutte le richieste |
  | `prediction_requests_total` | Totale richieste di inferenza completate con successo |
  | `rate(http_requests_total[5m])` | Richieste al secondo, media sugli ultimi 5 minuti |
  | `histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) by (le))` | Latenza p95 |
  | `100 * sum(rate(http_requests_total{status=~"5.."}[5m])) / sum(rate(http_requests_total[5m]))` | Percentuale di richieste in errore |

- **`/alerts`** — se in futuro configuri regole di allerta (es. "avvisami se il tasso di errore supera il 5%"), le trovi qui.

Prometheus è pensato più per il debug tecnico e le query ad-hoc; per un uso quotidiano/di monitoraggio conviene Grafana.

### ⚙️ Note tecniche

- Prometheus raccoglie le metriche dall'endpoint `http://yolo-api:8000/metrics`, esposto automaticamente da FastAPI grazie a `prometheus-fastapi-instrumentator`. Se questo endpoint risponde `404`, quasi sempre significa che il container `yolo-api` sta girando con un'immagine più vecchia delle modifiche — verifica con `docker inspect yolo_api --format='{{.Config.Image}}'` e rifai `docker compose pull && docker compose up -d --force-recreate yolo-api`.
- I dati in Prometheus sono conservati 30 giorni (configurabile in `docker-compose.yaml` con `--storage.tsdb.retention.time`); per lo storico a lungo termine fai riferimento a SQL Server, che non ha scadenza.
- Le credenziali del database e dell'admin Grafana vivono in `.env` (cifrato a riposo in `.env.enc`) e vengono distribuite ai container come Docker secrets (file in `/run/secrets/`), non come variabili d'ambiente in chiaro — eccetto il datasource SQL Server di Grafana, vedi nota sopra.
- Sia Grafana (`/grafana/`) che Prometheus (`/prometheus/`) passano esclusivamente da Nginx via HTTPS: nessuna delle due porte interne (3000, 9090) è esposta direttamente sull'host.
- Prometheus è protetto da autenticazione basic auth (file `nginx/.htpasswd`); Grafana ha il proprio sistema di login integrato.
- Il certificato TLS generato con `openssl` è **autofirmato**: perfetto per uso locale/interno, ma i browser mostreranno un avviso di sicurezza. Per un dominio pubblico, sostituiscilo con uno emesso da un'autorità riconosciuta (es. Let's Encrypt/Certbot, anche automatizzabile con un container `certbot` aggiuntivo nel compose).
- Se rigeneri `.env`, `nginx/certs/` o `nginx/.htpasswd`, ricordati di riavviare i servizi interessati (`docker compose up -d`) perché i container li leggono solo all'avvio.
