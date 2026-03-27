from __future__ import annotations

import os
from pathlib import Path


class Config:
    BASE_DIR = Path(__file__).resolve().parent.parent
    BACKEND_DIR = BASE_DIR / "backend"
    DATABASE_PATH = BASE_DIR / "crop_disease_ai.db"
    SECRET_KEY = os.getenv("SECRET_KEY", "change-this-in-production")

    UPLOAD_FOLDER = BASE_DIR / "uploads"
    FARMER_UPLOAD_FOLDER = UPLOAD_FOLDER / "farmer_uploads"
    ADMIN_UPLOAD_FOLDER = UPLOAD_FOLDER / "admin_uploads"

    DATASET_FOLDER = BASE_DIR / "dataset"
    DATASET_SEED_FOLDER = DATASET_FOLDER / "seed"
    DATASET_CUSTOM_FOLDER = DATASET_FOLDER / "custom"
    DATASET_MERGED_FOLDER = DATASET_FOLDER / "merged"
    DATASET_METADATA_PATH = DATASET_FOLDER / "dataset_metadata.json"

    MODELS_FOLDER = BASE_DIR / "models"
    MODEL_PATH = MODELS_FOLDER / "crop_disease_model.h5"
    CLASS_INDICES_PATH = MODELS_FOLDER / "class_indices.json"
    MODEL_METADATA_PATH = MODELS_FOLDER / "model_metadata.json"
    TRAINING_HISTORY_PATH = MODELS_FOLDER / "training_history.json"
    TRAINING_STATUS_PATH = MODELS_FOLDER / "training_status.json"
    CONFUSION_MATRIX_PATH = MODELS_FOLDER / "confusion_matrix.png"
    CHECKPOINT_PATH = MODELS_FOLDER / "best_model.keras"

    IMAGE_SIZE = (224, 224)
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "bmp", "webp"}
    TRAIN_SPLIT = 0.7
    VAL_SPLIT = 0.15
    TEST_SPLIT = 0.15
    BATCH_SIZE = 32
    EPOCHS = 12
    GUEST_SEARCH_LIMIT = int(os.getenv("GUEST_SEARCH_LIMIT", "5"))
    DEFAULT_ADMIN_USERNAME = os.getenv("DEFAULT_ADMIN_USERNAME", "admin")
    DEFAULT_ADMIN_PASSWORD = os.getenv("DEFAULT_ADMIN_PASSWORD", "Admin@123")

    @classmethod
    def ensure_directories(cls) -> None:
        for path in [
            cls.UPLOAD_FOLDER,
            cls.FARMER_UPLOAD_FOLDER,
            cls.ADMIN_UPLOAD_FOLDER,
            cls.DATASET_FOLDER,
            cls.DATASET_SEED_FOLDER,
            cls.DATASET_CUSTOM_FOLDER,
            cls.DATASET_MERGED_FOLDER,
            cls.MODELS_FOLDER,
        ]:
            path.mkdir(parents=True, exist_ok=True)
