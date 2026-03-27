from __future__ import annotations

from backend.database import query_db
from backend.utils.file_utils import read_json


class AnalyticsService:
    @staticmethod
    def dashboard_summary(model_metadata_path) -> dict:
        total_farmers = query_db("SELECT COUNT(*) AS count FROM Farmers", one=True)["count"]
        total_plants = query_db("SELECT COUNT(*) AS count FROM Plants", one=True)["count"]
        total_diseases = query_db("SELECT COUNT(*) AS count FROM Diseases", one=True)["count"]
        total_searches = query_db("SELECT COUNT(*) AS count FROM SearchHistory", one=True)["count"]
        total_dataset_images = query_db("SELECT COUNT(*) AS count FROM DatasetImages", one=True)["count"]
        total_custom_images = query_db(
            "SELECT COUNT(*) AS count FROM DatasetImages WHERE SourceType = 'custom'",
            one=True,
        )["count"]
        top_diseases = query_db(
            """
            SELECT d.DiseaseName, p.PlantName, COUNT(*) AS total
            FROM SearchHistory sh
            JOIN Diseases d ON d.DiseaseID = sh.DiseaseID
            JOIN Plants p ON p.PlantID = sh.PlantID
            GROUP BY sh.DiseaseID
            ORDER BY total DESC
            LIMIT 5
            """
        )
        active_farmers = query_db(
            """
            SELECT f.Name, f.Email, COUNT(*) AS total
            FROM SearchHistory sh
            JOIN Farmers f ON f.FarmerID = sh.FarmerID
            GROUP BY sh.FarmerID
            ORDER BY total DESC
            LIMIT 5
            """
        )
        usage_daily = query_db(
            """
            SELECT DATE(SearchDate) AS label, COUNT(*) AS total
            FROM SearchHistory
            GROUP BY DATE(SearchDate)
            ORDER BY DATE(SearchDate) DESC
            LIMIT 7
            """
        )
        usage_monthly = query_db(
            """
            SELECT strftime('%Y-%m', SearchDate) AS label, COUNT(*) AS total
            FROM SearchHistory
            GROUP BY strftime('%Y-%m', SearchDate)
            ORDER BY label DESC
            LIMIT 6
            """
        )
        latest_training = query_db(
            "SELECT * FROM TrainingRuns ORDER BY TrainingDate DESC LIMIT 1",
            one=True,
        )
        model_metadata = read_json(model_metadata_path, default={}) or {}

        return {
            "total_farmers": total_farmers,
            "total_plants": total_plants,
            "total_diseases": total_diseases,
            "total_searches": total_searches,
            "total_dataset_images": total_dataset_images,
            "total_custom_images": total_custom_images,
            "top_diseases": [dict(row) for row in top_diseases],
            "active_farmers": [dict(row) for row in active_farmers],
            "usage_daily": [dict(row) for row in usage_daily][::-1],
            "usage_monthly": [dict(row) for row in usage_monthly][::-1],
            "latest_training": dict(latest_training) if latest_training else None,
            "model_metadata": model_metadata,
        }

    @staticmethod
    def farmer_activity(farmer_id: int) -> dict:
        summary = query_db(
            """
            SELECT
                COUNT(*) AS total_searches,
                MAX(SearchDate) AS last_detection
            FROM SearchHistory
            WHERE FarmerID = ?
            """,
            (farmer_id,),
            one=True,
        )
        most_searched_plant = query_db(
            """
            SELECT p.PlantName, COUNT(*) AS total
            FROM SearchHistory sh
            JOIN Plants p ON p.PlantID = sh.PlantID
            WHERE sh.FarmerID = ?
            GROUP BY sh.PlantID
            ORDER BY total DESC
            LIMIT 1
            """,
            (farmer_id,),
            one=True,
        )
        most_detected_disease = query_db(
            """
            SELECT d.DiseaseName, COUNT(*) AS total
            FROM SearchHistory sh
            JOIN Diseases d ON d.DiseaseID = sh.DiseaseID
            WHERE sh.FarmerID = ?
            GROUP BY sh.DiseaseID
            ORDER BY total DESC
            LIMIT 1
            """,
            (farmer_id,),
            one=True,
        )
        return {
            "total_searches": summary["total_searches"] if summary else 0,
            "total_detections": summary["total_searches"] if summary else 0,
            "last_detection": summary["last_detection"] if summary else None,
            "most_searched_plant": dict(most_searched_plant) if most_searched_plant else None,
            "most_detected_disease": dict(most_detected_disease) if most_detected_disease else None,
        }

    @staticmethod
    def statistics_payload() -> dict:
        disease_frequency = query_db(
            """
            SELECT DATE(SearchDate) AS label, COUNT(*) AS total
            FROM SearchHistory
            GROUP BY DATE(SearchDate)
            ORDER BY label
            """
        )
        plant_usage = query_db(
            """
            SELECT p.PlantName AS label, COUNT(*) AS total
            FROM SearchHistory sh
            JOIN Plants p ON p.PlantID = sh.PlantID
            GROUP BY sh.PlantID
            ORDER BY total DESC
            """
        )
        model_usage = query_db(
            """
            SELECT COALESCE(ModelVersion, 'unknown') AS label, COUNT(*) AS total
            FROM SearchHistory
            GROUP BY COALESCE(ModelVersion, 'unknown')
            ORDER BY total DESC
            """
        )
        top_farmers = query_db(
            """
            SELECT f.Name AS label, COUNT(*) AS total
            FROM SearchHistory sh
            JOIN Farmers f ON f.FarmerID = sh.FarmerID
            GROUP BY sh.FarmerID
            ORDER BY total DESC
            LIMIT 10
            """
        )
        return {
            "disease_frequency": [dict(row) for row in disease_frequency],
            "plant_usage": [dict(row) for row in plant_usage],
            "model_usage": [dict(row) for row in model_usage],
            "top_farmers": [dict(row) for row in top_farmers],
        }
