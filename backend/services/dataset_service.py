from __future__ import annotations

import math
import random
import shutil
from dataclasses import dataclass
from pathlib import Path

from flask import current_app

from backend.database import execute_db, query_db
from backend.utils.file_utils import clear_directory, ensure_dir, make_safe_name, unique_file_path, write_json
from backend.utils.image_utils import resize_and_save_image, validate_image


@dataclass
class DatasetBuildSummary:
    total_images: int
    train_count: int
    val_count: int
    test_count: int
    classes: dict[str, int]


class DatasetService:
    @staticmethod
    def _has_registered_seed_images() -> bool:
        row = query_db(
            "SELECT COUNT(*) AS count FROM DatasetImages WHERE SourceType = 'seed'",
            one=True,
        )
        return bool(row and row["count"])

    @staticmethod
    def _get_or_create_plant(plant_name: str, description: str | None = None) -> int:
        plant = query_db("SELECT * FROM Plants WHERE PlantName = ?", (plant_name,), one=True)
        if plant:
            return plant["PlantID"]
        return execute_db(
            "INSERT INTO Plants (PlantName, Description) VALUES (?, ?)",
            (plant_name, description),
        )

    @staticmethod
    def _get_or_create_disease(
        plant_id: int,
        disease_name: str,
        *,
        symptoms: str = "",
        treatment: str = "",
        supplement: str = "",
        notes: str = "",
    ) -> int:
        disease = query_db(
            "SELECT * FROM Diseases WHERE PlantID = ? AND DiseaseName = ?",
            (plant_id, disease_name),
            one=True,
        )
        if disease:
            return disease["DiseaseID"]
        return execute_db(
            """
            INSERT INTO Diseases (PlantID, DiseaseName, Symptoms, Treatment, Supplement, Notes)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (plant_id, disease_name, symptoms, treatment, supplement, notes),
        )

    @staticmethod
    def _upsert_dataset_image(plant_id: int, disease_id: int, image_path: str, source_type: str) -> None:
        existing = query_db(
            "SELECT ImageID FROM DatasetImages WHERE ImagePath = ?",
            (image_path,),
            one=True,
        )
        if existing:
            execute_db(
                """
                UPDATE DatasetImages
                SET PlantID = ?, DiseaseID = ?, SourceType = ?, IsValidated = 1
                WHERE ImageID = ?
                """,
                (plant_id, disease_id, source_type, existing["ImageID"]),
            )
            return
        execute_db(
            """
            INSERT INTO DatasetImages (PlantID, DiseaseID, ImagePath, SourceType, IsValidated)
            VALUES (?, ?, ?, ?, 1)
            """,
            (plant_id, disease_id, image_path, source_type),
        )

    @staticmethod
    def _iter_images(directory: Path):
        for path in directory.rglob("*"):
            if path.is_file() and path.suffix.lower().lstrip(".") in current_app.config["ALLOWED_IMAGE_EXTENSIONS"]:
                yield path

    @staticmethod
    def _parse_class_tokens(path: Path, base_dir: Path) -> tuple[str, str]:
        relative = path.relative_to(base_dir)
        parts = relative.parts
        if len(parts) >= 3:
            return parts[0].replace("_", " ").title(), parts[1].replace("_", " ").title()

        class_name = parts[0]
        if "___" in class_name:
            plant, disease = class_name.split("___", 1)
            return plant.replace("_", " ").title(), disease.replace("_", " ").title()
        raise ValueError(f"Unsupported dataset structure for {path}")

    @classmethod
    def import_plantvillage(cls, source_dir: str | Path) -> dict:
        source_path = Path(source_dir)
        if not source_path.exists():
            raise FileNotFoundError(f"PlantVillage स्रोत फोल्डर सापडला नाही: {source_path}")

        imported = 0
        seed_root = Path(current_app.config["DATASET_SEED_FOLDER"])

        for image_path in cls._iter_images(source_path):
            if not validate_image(image_path):
                continue
            plant_name, disease_name = cls._parse_class_tokens(image_path, source_path)
            plant_id = cls._get_or_create_plant(plant_name)
            disease_id = cls._get_or_create_disease(plant_id, disease_name)

            destination = unique_file_path(
                seed_root / make_safe_name(plant_name) / make_safe_name(disease_name),
                image_path.name,
            )
            resize_and_save_image(image_path, destination)
            cls._upsert_dataset_image(plant_id, disease_id, str(destination), "seed")
            imported += 1

        return {"imported_images": imported, "source": str(source_path)}

    @classmethod
    def sync_existing_seed_dataset(cls, source_dir: str | Path | None = None) -> dict:
        seed_root = Path(source_dir) if source_dir else Path(current_app.config["DATASET_SEED_FOLDER"])
        if not seed_root.exists():
            raise FileNotFoundError(f"Seed dataset directory not found: {seed_root}")

        synced = 0
        for image_path in cls._iter_images(seed_root):
            if not validate_image(image_path):
                continue
            plant_name, disease_name = cls._parse_class_tokens(image_path, seed_root)
            plant_id = cls._get_or_create_plant(plant_name)
            disease_id = cls._get_or_create_disease(plant_id, disease_name)
            cls._upsert_dataset_image(plant_id, disease_id, str(image_path), "seed")
            synced += 1

        return {"synced_images": synced, "source": str(seed_root)}

    @classmethod
    def ensure_seed_dataset_registered(cls) -> dict:
        if cls._has_registered_seed_images():
            return {"synced": False, "reason": "already_registered"}

        seed_root = Path(current_app.config["DATASET_SEED_FOLDER"])
        if not seed_root.exists():
            return {"synced": False, "reason": "missing_seed_directory"}

        try:
            next(cls._iter_images(seed_root))
        except StopIteration:
            return {"synced": False, "reason": "empty_seed_directory"}

        result = cls.sync_existing_seed_dataset(seed_root)
        return {"synced": True, **result}

    @classmethod
    def add_custom_image(cls, file_storage, plant_id: int, disease_id: int) -> dict:
        if not file_storage or not file_storage.filename:
            raise ValueError("कोणताही डेटासेट फोटो अपलोड केलेला नाही.")

        plant = query_db("SELECT * FROM Plants WHERE PlantID = ?", (plant_id,), one=True)
        disease = query_db("SELECT * FROM Diseases WHERE DiseaseID = ?", (disease_id,), one=True)
        if not plant or not disease:
            raise ValueError("अवैध पीक किंवा रोग निवड.")

        destination = unique_file_path(
            Path(current_app.config["DATASET_CUSTOM_FOLDER"])
            / make_safe_name(plant["PlantName"])
            / make_safe_name(disease["DiseaseName"]),
            file_storage.filename,
        )
        file_storage.save(destination)
        if not validate_image(destination):
            destination.unlink(missing_ok=True)
            raise ValueError("अपलोड केलेली फाइल वैध प्रतिमा नाही.")
        resize_and_save_image(destination, destination)
        cls._upsert_dataset_image(plant_id, disease_id, str(destination), "custom")
        return {"path": str(destination)}

    @classmethod
    def delete_dataset_image(cls, image_id: int) -> None:
        image = query_db("SELECT * FROM DatasetImages WHERE ImageID = ?", (image_id,), one=True)
        if not image:
            return
        path = Path(image["ImagePath"])
        if path.exists():
            path.unlink()
        execute_db("DELETE FROM DatasetImages WHERE ImageID = ?", (image_id,))

    @classmethod
    def rebuild_merged_dataset(cls) -> DatasetBuildSummary:
        merged_root = Path(current_app.config["DATASET_MERGED_FOLDER"])
        clear_directory(merged_root)
        train_root = ensure_dir(merged_root / "train")
        val_root = ensure_dir(merged_root / "val")
        test_root = ensure_dir(merged_root / "test")

        rows = query_db(
            """
            SELECT di.ImagePath, p.PlantName, d.DiseaseName
            FROM DatasetImages di
            JOIN Plants p ON p.PlantID = di.PlantID
            JOIN Diseases d ON d.DiseaseID = di.DiseaseID
            WHERE di.IsValidated = 1
            ORDER BY p.PlantName, d.DiseaseName, di.ImageID
            """
        )

        grouped: dict[str, list[dict]] = {}
        for row in rows:
            class_name = f"{make_safe_name(row['PlantName'])}___{make_safe_name(row['DiseaseName'])}"
            grouped.setdefault(class_name, []).append(dict(row))

        train_count = 0
        val_count = 0
        test_count = 0
        class_summary: dict[str, int] = {}

        for class_name, class_rows in grouped.items():
            random.shuffle(class_rows)
            total = len(class_rows)
            class_summary[class_name] = total

            if total == 1:
                split_map = {"train": class_rows, "val": class_rows, "test": class_rows}
            else:
                train_end = max(1, math.floor(total * current_app.config["TRAIN_SPLIT"]))
                val_end = train_end + max(1, math.floor(total * current_app.config["VAL_SPLIT"]))
                split_map = {
                    "train": class_rows[:train_end],
                    "val": class_rows[train_end:val_end] or class_rows[:1],
                    "test": class_rows[val_end:] or class_rows[-1:],
                }

            for split_name, split_rows in split_map.items():
                split_root = {"train": train_root, "val": val_root, "test": test_root}[split_name] / class_name
                ensure_dir(split_root)
                for row in split_rows:
                    source = Path(row["ImagePath"])
                    if not source.exists():
                        continue
                    target = split_root / source.name
                    shutil.copy2(source, target)
                    if split_name == "train":
                        train_count += 1
                    elif split_name == "val":
                        val_count += 1
                    else:
                        test_count += 1

        payload = {
            "total_images": train_count + val_count + test_count,
            "train_count": train_count,
            "val_count": val_count,
            "test_count": test_count,
            "classes": class_summary,
        }
        write_json(current_app.config["DATASET_METADATA_PATH"], payload)
        return DatasetBuildSummary(**payload)

    @staticmethod
    def get_dataset_statistics() -> dict:
        total_images = query_db("SELECT COUNT(*) AS count FROM DatasetImages", one=True)["count"]
        custom_images = query_db(
            "SELECT COUNT(*) AS count FROM DatasetImages WHERE SourceType = 'custom'",
            one=True,
        )["count"]
        per_class_rows = query_db(
            """
            SELECT di.ImageID, di.ImagePath, di.SourceType, p.PlantName, d.DiseaseName
            FROM DatasetImages di
            JOIN Plants p ON p.PlantID = di.PlantID
            JOIN Diseases d ON d.DiseaseID = di.DiseaseID
            ORDER BY di.UploadDate DESC
            """
        )
        counts = query_db(
            """
            SELECT p.PlantName, d.DiseaseName, COUNT(*) AS image_count
            FROM DatasetImages di
            JOIN Plants p ON p.PlantID = di.PlantID
            JOIN Diseases d ON d.DiseaseID = di.DiseaseID
            GROUP BY p.PlantName, d.DiseaseName
            ORDER BY image_count DESC, p.PlantName, d.DiseaseName
            """
        )
        return {
            "total_images": total_images,
            "custom_images": custom_images,
            "classes": [dict(row) for row in counts],
            "images": [dict(row) for row in per_class_rows[:30]],
        }
