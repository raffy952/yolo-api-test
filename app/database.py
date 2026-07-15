import os
import json
import time
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, DateTime, text
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.engine.url import make_url
from sqlalchemy.exc import OperationalError

DATABASE_URL = os.getenv("DB_CONNECTION_STRING")

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
            break # Esce dal ciclo se la connessione e la verifica hanno successo
            
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