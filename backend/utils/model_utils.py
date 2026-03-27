from __future__ import annotations

from pathlib import Path

from tensorflow.keras import Sequential
from tensorflow.keras.layers import Conv2D, Dense, Dropout, Flatten, MaxPooling2D

from backend.utils.file_utils import read_json


def build_custom_cnn(input_shape: tuple[int, int, int], num_classes: int) -> Sequential:
    model = Sequential(
        [
            Conv2D(32, (3, 3), activation="relu", input_shape=input_shape),
            MaxPooling2D((2, 2)),
            Conv2D(64, (3, 3), activation="relu"),
            MaxPooling2D((2, 2)),
            Conv2D(128, (3, 3), activation="relu"),
            MaxPooling2D((2, 2)),
            Flatten(),
            Dense(256, activation="relu"),
            Dropout(0.4),
            Dense(num_classes, activation="softmax"),
        ]
    )
    model.compile(
        optimizer="adam",
        loss="categorical_crossentropy",
        metrics=["accuracy"],
    )
    return model


def parse_class_label(label: str) -> tuple[str, str]:
    if "___" in label:
        plant, disease = label.split("___", 1)
    elif "__" in label:
        plant, disease = label.split("__", 1)
    else:
        plant, disease = "unknown", label
    return plant.replace("_", " ").title(), disease.replace("_", " ").title()


def get_latest_model_version(metadata_path: str | Path) -> str:
    metadata = read_json(metadata_path, default={}) or {}
    return metadata.get("model_version", "untrained")
