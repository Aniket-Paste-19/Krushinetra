from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
from flask import current_app

from backend.utils.file_utils import ensure_dir


def validate_image(path: str | Path) -> bool:
    image = cv2.imread(str(path))
    return image is not None


def resize_and_save_image(source: str | Path, destination: str | Path) -> Path:
    image = cv2.imread(str(source))
    if image is None:
        raise ValueError(f"अवैध प्रतिमा फाइल: {source}")
    resized = cv2.resize(image, current_app.config["IMAGE_SIZE"])
    ensure_dir(Path(destination).parent)
    cv2.imwrite(str(destination), resized)
    return Path(destination)


def preprocess_image_for_model(path: str | Path) -> np.ndarray:
    image = cv2.imread(str(path))
    if image is None:
        raise ValueError("अपलोड केलेली प्रतिमा वाचता आली नाही.")
    image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    image = cv2.resize(image, current_app.config["IMAGE_SIZE"])
    image = image.astype("float32") / 255.0
    return np.expand_dims(image, axis=0)
