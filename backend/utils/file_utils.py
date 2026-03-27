from __future__ import annotations

import json
import shutil
from pathlib import Path
from uuid import uuid4

from flask import current_app


def ensure_dir(path: str | Path) -> Path:
    resolved = Path(path)
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def clear_directory(path: str | Path) -> Path:
    resolved = ensure_dir(path)
    for item in resolved.iterdir():
        if item.is_dir():
            shutil.rmtree(item)
        else:
            item.unlink()
    return resolved


def is_allowed_image(filename: str) -> bool:
    if "." not in filename:
        return False
    extension = filename.rsplit(".", 1)[1].lower()
    return extension in current_app.config["ALLOWED_IMAGE_EXTENSIONS"]


def make_safe_name(value: str) -> str:
    value = value.strip().replace("&", "and").replace("/", "-")
    parts = [part for part in value.replace("__", "_").split() if part]
    safe = "_".join(parts).lower()
    return "".join(char for char in safe if char.isalnum() or char in {"_", "-"})


def unique_file_path(directory: str | Path, filename: str) -> Path:
    safe_name = Path(filename).name
    stem = Path(safe_name).stem
    suffix = Path(safe_name).suffix.lower()
    return ensure_dir(directory) / f"{make_safe_name(stem)}_{uuid4().hex[:8]}{suffix}"


def write_json(path: str | Path, payload) -> None:
    target = Path(path)
    ensure_dir(target.parent)
    target.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def read_json(path: str | Path, default=None):
    target = Path(path)
    if not target.exists():
        return default
    return json.loads(target.read_text(encoding="utf-8"))


def copy_file(source: str | Path, target: str | Path) -> Path:
    ensure_dir(Path(target).parent)
    shutil.copy2(source, target)
    return Path(target)
