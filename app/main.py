import numpy as np
import cv2
import json
from fastapi import FastAPI, UploadFile, File, HTTPException, Depends
from sqlalchemy.orm import Session
from ultralytics import YOLO

# Import dal tuo file database.py
from database import PredictionLog, get_db

app = FastAPI(title="YOLO Person Detection API")

# PRE-CARICAMENTO: Il modello viene caricato in memoria all'avvio del container.
model = YOLO("yolov8n.pt")

@app.get("/health")
def health_check():
    return {"status": "healthy", "model": "yolov8n"}

# UNICO ENDPOINT UNIFICATO
@app.post("/predict/person")
async def predict_person(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Il file inviato non è un'immagine")

    try:
        # 1. Leggi i byte direttamente in RAM ed effettua il decode con OpenCV
        contents = await file.read()
        nparr = np.frombuffer(contents, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if img is None:
            raise ValueError("Impossibile decodificare l'immagine")

        # 2. Inferenza: classes=[0] forza YOLO a cercare solo persone. conf=0.5 imposta la soglia.
        results = model.predict(source=img, classes=[0], conf=0.5, verbose=False)
        
        # 3. Estrazione delle Bounding Box
        detections = []
        for result in results:
            for box in result.boxes:
                # Estrai le coordinate (x_min, y_min, x_max, y_max)
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                conf = float(box.conf[0])
                
                detections.append({
                    "bbox": [int(x1), int(y1), int(x2), int(y2)],
                    "confidence": round(conf, 2)
                })

        # 4. SALVATAGGIO A DATABASE
        persons_count = len(detections)
        new_log = PredictionLog(
            persons_detected=persons_count,
            detections_json=json.dumps(detections)
        )
        db.add(new_log)
        db.commit()
        
        # Ottiene l'ID autogenerato da SQL Server
        db.refresh(new_log) 

        return {
            "log_id": new_log.id,
            "persons_detected": persons_count, 
            "detections": detections
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore durante l'elaborazione: {str(e)}")