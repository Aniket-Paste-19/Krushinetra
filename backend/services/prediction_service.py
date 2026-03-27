from __future__ import annotations

from pathlib import Path

import numpy as np
from flask import current_app
from tensorflow.keras.models import load_model

from backend.database import execute_db, query_db
from backend.utils.file_utils import read_json
from backend.utils.image_utils import preprocess_image_for_model
from backend.utils.model_utils import get_latest_model_version, parse_class_label


class PredictionService:
    _model = None
    _class_indices = None
    _loaded_version = None

    @classmethod
    def _load_assets(cls):
        model_path = Path(current_app.config["MODEL_PATH"])
        class_indices_path = Path(current_app.config["CLASS_INDICES_PATH"])
        if not model_path.exists() or not class_indices_path.exists():
            raise FileNotFoundError("ट्रेनिंग झालेले मॉडेल उपलब्ध नाही. कृपया प्रथम मॉडेल ट्रेन करा.")
        model_version = get_latest_model_version(current_app.config["MODEL_METADATA_PATH"])
        version_changed = cls._loaded_version != model_version
        if cls._model is None or version_changed:
            cls._model = load_model(model_path)
            cls._loaded_version = model_version
        if cls._class_indices is None or version_changed:
            cls._class_indices = read_json(class_indices_path, default={}) or {}
        return cls._model, cls._class_indices

    @classmethod
    def predict(
        cls,
        image_path: str | Path,
        farmer_id: int | None = None,
        selected_plant_id: int | None = None,
    ) -> dict:
        model, class_indices = cls._load_assets()
        input_tensor = preprocess_image_for_model(image_path)
        probabilities = model.predict(input_tensor, verbose=0)[0]
        predicted_index = int(np.argmax(probabilities))
        confidence = float(probabilities[predicted_index])
        reverse_mapping = {index: label for label, index in class_indices.items()}
        class_label = reverse_mapping[predicted_index]
        predicted_plant_name, predicted_disease_name = parse_class_label(class_label)

        disease = query_db(
            """
            SELECT d.*, p.PlantName
            FROM Diseases d
            JOIN Plants p ON p.PlantID = d.PlantID
            WHERE LOWER(p.PlantName) = LOWER(?) AND LOWER(d.DiseaseName) = LOWER(?)
            LIMIT 1
            """,
            (predicted_plant_name, predicted_disease_name),
            one=True,
        )
        if disease is None and selected_plant_id:
            disease = query_db(
                """
                SELECT d.*, p.PlantName
                FROM Diseases d
                JOIN Plants p ON p.PlantID = d.PlantID
                WHERE d.PlantID = ?
                ORDER BY CASE WHEN LOWER(d.DiseaseName) = LOWER(?) THEN 0 ELSE 1 END, d.DiseaseID
                LIMIT 1
                """,
                (selected_plant_id, predicted_disease_name),
                one=True,
            )
        if disease is None:
            raise LookupError("भाकीत केलेला वर्ग डेटाबेसमधील पीक आणि रोगाशी जुळवता आला नाही.")

        model_version = get_latest_model_version(current_app.config["MODEL_METADATA_PATH"])
        if farmer_id is not None:
            execute_db(
                """
                INSERT INTO SearchHistory (
                    FarmerID, PlantID, DiseaseID, ImagePath, PredictionConfidence, ModelVersion, SourceType
                )
                VALUES (?, ?, ?, ?, ?, ?, 'prediction')
                """,
                (
                    farmer_id,
                    disease["PlantID"],
                    disease["DiseaseID"],
                    str(image_path),
                    confidence,
                    model_version,
                ),
            )

        return {
            "plant_name": disease["PlantName"],
            "disease_name": disease["DiseaseName"],
            "confidence_score": round(confidence * 100, 2),
            "symptoms": disease["Symptoms"],
            "treatment": disease["Treatment"],
            "supplement": disease["Supplement"],
            "notes": disease["Notes"],
            "model_version": model_version,
        }
