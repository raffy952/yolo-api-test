import os
import json
import time
from datetime import datetime
from urllib.parse import quote_plus
from sqlalchemy import create_engine, Column, Integer, String, DateTime, text
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.engine.url import make_url
from sqlalchemy.exc import OperationalError


def _read_secret(file_env_var: str, plain_env_var: str, default: str = None) -> str:
    """
    Legge un valore sensibile preferendo un Docker secret montato come file
    (indicato da una env var che finisce in _FILE, es. DB_PASSWORD_FILE=/run/secrets/db_password).
    Se il file non esiste, ricade sulla variabile d'ambiente semplice (compatibilità
    con setup senza secrets, es. sviluppo locale rapido).
    """
    file_path = os.getenv(file_env_var)
    if file_path and os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read().strip()
    return os.getenv(plain_env_var, default)


# Credenziali sensibili: preferisce i Docker secrets (file), altrimenti env var diretta
DB_USER = _read_secret("DB_USER_FILE", "DB_USER")
DB_PASSWORD = _read_secret("DB_PASSWORD_FILE", "DB_PASSWORD")

# Parametri non sensibili: solo env var, nessun bisogno di un secret per questi
DB_SERVER = os.getenv("DB_SERVER", "host.docker.internal")
DB_PORT = os.getenv("DB_PORT", "1433")
DB_NAME = os.getenv("DB_NAME", "YoloVisionDB")

if not DB_USER or not DB_PASSWORD:
    raise RuntimeError(
        "Credenziali database mancanti: imposta DB_USER_FILE/DB_PASSWORD_FILE "
        "(Docker secrets) oppure DB_USER/DB_PASSWORD come variabili d'ambiente."
    )

# quote_plus per gestire in sicurezza eventuali caratteri speciali in utente/password (@, :, /, ecc.)
DATABASE_URL = (
    f"mssql+pyodbc://{quote_plus(DB_USER)}:{quote_plus(DB_PASSWORD)}"
    f"@{DB_SERVER}:{DB_PORT}/{DB_NAME}"
    f"?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes"
)


def create_database_if_not_exists(url_string: str):
    """
    Si connette al DB 'master' di SQL Server per creare il database target se non esiste.
    """
    url = make_url(url_string)
    target_db = url.database

    # Per creare un database, SQL Server richiede la connessione a 'master'
    master_url = url.set(database="master")

    # L'isolamento AUTOCOMMIT è obbligatorio, altrimenti SQL Server rifiuta il comando CREATE DATABASE
    master_engine = create_engine(master_url, isolation_level="AUTOCOMMIT")

    max_retries = 5
    for i in range(max_retries):
        try:
            with master_engine.connect() as conn:
                # Controlla se il database esiste già nella tabella di sistema
                check_query = text(f"SELECT name FROM sys.databases WHERE name = N'{target_db}'")
                result = conn.execute(check_query)

                if not result.fetchone():
                    print(f"Database '{target_db}' non trovato. Creazione in corso...")
                    # Crea il database usando raw SQL
                    conn.execute(text(f"CREATE DATABASE [{target_db}]"))
                else:
                    print(f"Database '{target_db}' verificato.")
            break  # Esce dal ciclo se la connessione e la verifica hanno successo

        except OperationalError as e:
            if i == max_retries - 1:
                raise e
            print(f"Connessione a SQL Server fallita, riprovo tra 3 secondi... ({i+1}/{max_retries})")
            time.sleep(3)

    master_engine.dispose()


# 1. Eseguiamo il controllo (e l'eventuale creazione) del database
create_database_if_not_exists(DATABASE_URL)

# 2. Ora possiamo connetterci normalmente al nostro database target
engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# Definisce la struttura della tabella
class PredictionLog(Base):
    __tablename__ = "yolo_predictions"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    persons_detected = Column(Integer)
    detections_json = Column(String(length=4000))


# 3. Crea le tabelle all'interno del database (se non esistono già)
Base.metadata.create_all(bind=engine)


# Dependency da iniettare in FastAPI
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
