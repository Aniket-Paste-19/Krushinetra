from __future__ import annotations

import threading
from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from flask import current_app
from sklearn.metrics import ConfusionMatrixDisplay, confusion_matrix
from tensorflow.keras.callbacks import Callback, EarlyStopping, ModelCheckpoint
from tensorflow.keras.preprocessing.image import ImageDataGenerator

from backend.database import execute_db
from backend.services.dataset_service import DatasetService
from backend.utils.file_utils import read_json, write_json
from backend.utils.model_utils import build_custom_cnn


class TrainingStatusCallback(Callback):
    def __init__(self, status_path: str | Path):
        super().__init__()
        self.status_path = status_path

    def on_epoch_end(self, epoch, logs=None):
        payload = read_json(self.status_path, default={}) or {}
        payload["current_epoch"] = epoch + 1
        payload["status"] = "training"
        payload["metrics"] = {key: float(value) for key, value in (logs or {}).items()}
        write_json(self.status_path, payload)


class TrainingService:
    _lock = threading.Lock()
    _thread: threading.Thread | None = None

    @classmethod
    def current_status(cls) -> dict:
        return read_json(
            current_app.config["TRAINING_STATUS_PATH"],
            default={"status": "idle", "message": "अजून ट्रेनिंग सुरू झालेले नाही."},
        ) or {"status": "idle", "message": "अजून ट्रेनिंग सुरू झालेले नाही."}

    @classmethod
    def start_async_training(cls) -> dict:
        with cls._lock:
            if cls._thread and cls._thread.is_alive():
                return {"started": False, "message": "ट्रेनिंग आधीपासून सुरू आहे."}
            app = current_app._get_current_object()
            cls._thread = threading.Thread(target=cls._run_training_job, args=(app,), daemon=True)
            cls._thread.start()
        return {"started": True, "message": "ट्रेनिंग सुरू झाले."}

    @classmethod
    def _run_training_job(cls, app):
        with app.app_context():
            status_path = current_app.config["TRAINING_STATUS_PATH"]
            try:
                write_json(status_path, {"status": "preparing", "message": "मर्ज केलेले डेटासेट तयार होत आहे..."})
                dataset_summary = DatasetService.rebuild_merged_dataset()
                result = cls.train_model(dataset_summary)
                write_json(
                    status_path,
                    {
                        "status": "completed",
                        "message": "ट्रेनिंग यशस्वीरीत्या पूर्ण झाले.",
                        "result": result,
                    },
                )
            except Exception as exc:  # noqa: BLE001
                write_json(
                    status_path,
                    {
                        "status": "failed",
                        "message": str(exc),
                    },
                )

    @classmethod
    def train_model(cls, dataset_summary=None) -> dict:
        if dataset_summary is None:
            dataset_summary = DatasetService.rebuild_merged_dataset()

        merged_root = Path(current_app.config["DATASET_MERGED_FOLDER"])
        train_dir = merged_root / "train"
        val_dir = merged_root / "val"
        test_dir = merged_root / "test"

        if not train_dir.exists() or not any(train_dir.iterdir()):
            raise ValueError("मर्ज केलेले डेटासेट रिकामे आहे. प्रथम प्रतिमा आयात किंवा अपलोड करा.")

        train_generator = ImageDataGenerator(
            rescale=1.0 / 255.0,
            rotation_range=20,
            width_shift_range=0.1,
            height_shift_range=0.1,
            shear_range=0.1,
            zoom_range=0.15,
            horizontal_flip=True,
        ).flow_from_directory(
            train_dir,
            target_size=current_app.config["IMAGE_SIZE"],
            batch_size=current_app.config["BATCH_SIZE"],
            class_mode="categorical",
        )
        val_generator = ImageDataGenerator(rescale=1.0 / 255.0).flow_from_directory(
            val_dir,
            target_size=current_app.config["IMAGE_SIZE"],
            batch_size=current_app.config["BATCH_SIZE"],
            class_mode="categorical",
            shuffle=False,
        )
        test_generator = ImageDataGenerator(rescale=1.0 / 255.0).flow_from_directory(
            test_dir,
            target_size=current_app.config["IMAGE_SIZE"],
            batch_size=current_app.config["BATCH_SIZE"],
            class_mode="categorical",
            shuffle=False,
        )

        model = build_custom_cnn(
            input_shape=(
                current_app.config["IMAGE_SIZE"][0],
                current_app.config["IMAGE_SIZE"][1],
                3,
            ),
            num_classes=train_generator.num_classes,
        )
        callbacks = [
            EarlyStopping(monitor="val_accuracy", patience=3, restore_best_weights=True),
            ModelCheckpoint(current_app.config["CHECKPOINT_PATH"], monitor="val_accuracy", save_best_only=True),
            TrainingStatusCallback(current_app.config["TRAINING_STATUS_PATH"]),
        ]
        write_json(
            current_app.config["TRAINING_STATUS_PATH"],
            {"status": "training", "message": "मॉडेल ट्रेनिंग सुरू झाले.", "epochs": current_app.config["EPOCHS"]},
        )
        history = model.fit(
            train_generator,
            validation_data=val_generator,
            epochs=current_app.config["EPOCHS"],
            callbacks=callbacks,
            verbose=1,
        )

        test_loss, test_accuracy = model.evaluate(test_generator, verbose=0)
        predictions = model.predict(test_generator, verbose=0)
        predicted_labels = np.argmax(predictions, axis=1)
        matrix = confusion_matrix(test_generator.classes, predicted_labels)

        figure_size = max(6, min(16, test_generator.num_classes))
        disp = ConfusionMatrixDisplay(confusion_matrix=matrix, display_labels=list(test_generator.class_indices.keys()))
        figure, axis = plt.subplots(figsize=(figure_size, figure_size))
        disp.plot(ax=axis, xticks_rotation=90, colorbar=False)
        figure.tight_layout()
        figure.savefig(current_app.config["CONFUSION_MATRIX_PATH"])
        plt.close(figure)

        model.save(current_app.config["MODEL_PATH"])

        model_version = f"v{datetime.now().strftime('%Y%m%d%H%M%S')}"
        metadata = {
            "model_version": model_version,
            "last_training_date": datetime.now().isoformat(),
            "accuracy": float(test_accuracy),
            "loss": float(test_loss),
            "class_count": train_generator.num_classes,
            "status": "ready",
        }
        history_payload = {key: [float(item) for item in value] for key, value in history.history.items()}

        write_json(current_app.config["CLASS_INDICES_PATH"], train_generator.class_indices)
        write_json(current_app.config["MODEL_METADATA_PATH"], metadata)
        write_json(current_app.config["TRAINING_HISTORY_PATH"], history_payload)

        execute_db(
            """
            INSERT INTO TrainingRuns (
                ModelVersion, DatasetImageCount, TrainCount, ValCount, TestCount,
                Accuracy, Loss, ModelPath, Notes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                model_version,
                dataset_summary.total_images,
                dataset_summary.train_count,
                dataset_summary.val_count,
                dataset_summary.test_count,
                float(test_accuracy),
                float(test_loss),
                str(current_app.config["MODEL_PATH"]),
                "Custom CNN training run",
            ),
        )

        return {
            "model_version": model_version,
            "accuracy": round(float(test_accuracy) * 100, 2),
            "loss": round(float(test_loss), 4),
            "dataset": {
                "total": dataset_summary.total_images,
                "train": dataset_summary.train_count,
                "val": dataset_summary.val_count,
                "test": dataset_summary.test_count,
            },
        }
