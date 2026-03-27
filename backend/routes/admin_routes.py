from __future__ import annotations

import sqlite3

from flask import Blueprint, current_app, flash, jsonify, redirect, render_template, request, session, url_for

from backend.database import execute_db, query_db
from backend.services.analytics_service import AnalyticsService
from backend.services.auth_service import admin_login_required, authenticate_admin
from backend.services.dataset_service import DatasetService
from backend.services.training_service import TrainingService

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


def _wants_json() -> bool:
    return request.is_json or request.args.get("format") == "json" or "application/json" in request.headers.get("Accept", "")


def _ensure_seed_dataset_available(*, notify: bool = False) -> dict:
    result = DatasetService.ensure_seed_dataset_registered()
    if notify and result.get("synced"):
        flash(f"सीड डेटासेट सिंक झाले: {result['synced_images']} प्रतिमा नोंदल्या गेल्या.", "success")
    return result


@admin_bp.route("/login", methods=["GET", "POST"])
def login_page():
    if request.method == "POST":
        payload = request.get_json(silent=True) or request.form
        admin = authenticate_admin(payload["username"], payload["password"])
        if not admin:
            if _wants_json():
                return jsonify({"error": "चुकीची अॅडमिन लॉगिन माहिती."}), 401
            flash("चुकीची अॅडमिन लॉगिन माहिती.", "danger")
            return render_template("admin/login.html")

        session.clear()
        session["admin_id"] = admin["AdminID"]
        session["admin_username"] = admin["Username"]
        if _wants_json():
            return jsonify({"message": "लॉगिन यशस्वी झाले."})
        return redirect(url_for("admin.dashboard"))
    return render_template("admin/login.html")


@admin_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("admin.login_page"))


@admin_bp.route("/dashboard")
@admin_login_required
def dashboard():
    _ensure_seed_dataset_available(notify=True)
    summary = AnalyticsService.dashboard_summary(current_app.config["MODEL_METADATA_PATH"])
    return render_template("admin/dashboard.html", summary=summary)


@admin_bp.route("/farmers")
@admin_login_required
def farmers():
    search_term = request.args.get("q", "").strip()
    if search_term:
        rows = query_db(
            """
            SELECT f.*, COUNT(sh.SearchID) AS searches
            FROM Farmers f
            LEFT JOIN SearchHistory sh ON sh.FarmerID = f.FarmerID
            WHERE f.Name LIKE ? OR f.Email LIKE ? OR COALESCE(f.Phone, '') LIKE ?
            GROUP BY f.FarmerID
            ORDER BY f.CreatedDate DESC
            """,
            tuple(f"%{search_term}%" for _ in range(3)),
        )
    else:
        rows = query_db(
            """
            SELECT f.*, COUNT(sh.SearchID) AS searches
            FROM Farmers f
            LEFT JOIN SearchHistory sh ON sh.FarmerID = f.FarmerID
            GROUP BY f.FarmerID
            ORDER BY f.CreatedDate DESC
            """
        )
    farmers_data = [dict(row) for row in rows]
    if _wants_json():
        return jsonify(farmers_data)
    return render_template("admin/farmers.html", farmers=farmers_data, search_term=search_term)


@admin_bp.route("/farmers/block/<int:farmer_id>", methods=["POST"])
@admin_login_required
def block_farmer(farmer_id: int):
    execute_db("UPDATE Farmers SET Status = 'blocked' WHERE FarmerID = ?", (farmer_id,))
    if _wants_json():
        return jsonify({"message": "शेतकरी ब्लॉक केला."})
    flash("शेतकरी ब्लॉक केला.", "warning")
    return redirect(url_for("admin.farmers"))


@admin_bp.route("/farmers/unblock/<int:farmer_id>", methods=["POST"])
@admin_login_required
def unblock_farmer(farmer_id: int):
    execute_db("UPDATE Farmers SET Status = 'active' WHERE FarmerID = ?", (farmer_id,))
    if _wants_json():
        return jsonify({"message": "शेतकरी अनब्लॉक केला."})
    flash("शेतकरी अनब्लॉक केला.", "success")
    return redirect(url_for("admin.farmers"))


@admin_bp.route("/farmers/<int:farmer_id>", methods=["DELETE"])
@admin_login_required
def delete_farmer(farmer_id: int):
    execute_db("DELETE FROM Farmers WHERE FarmerID = ?", (farmer_id,))
    return jsonify({"message": "शेतकरी हटवला."})


@admin_bp.route("/plants", methods=["GET"])
@admin_login_required
def plants():
    rows = query_db("SELECT * FROM Plants ORDER BY PlantName")
    plants_data = [dict(row) for row in rows]
    if _wants_json():
        return jsonify(plants_data)
    return render_template("admin/plants.html", plants=plants_data)


@admin_bp.route("/add-plant", methods=["POST"])
@admin_login_required
def add_plant():
    payload = request.get_json(silent=True) or request.form
    try:
        plant_id = execute_db(
            "INSERT INTO Plants (PlantName, Description) VALUES (?, ?)",
            (payload["plant_name"], payload.get("description")),
        )
    except sqlite3.IntegrityError:
        return jsonify({"error": "पीकाचे नाव आधीच अस्तित्वात आहे."}), 409
    if _wants_json():
        return jsonify({"message": "पीक जोडले.", "plant_id": plant_id}), 201
    flash("पीक यशस्वीरीत्या जोडले.", "success")
    return redirect(url_for("admin.plants"))


@admin_bp.route("/update-plant/<int:plant_id>", methods=["PUT", "POST"])
@admin_login_required
def update_plant(plant_id: int):
    payload = request.get_json(silent=True) or request.form
    execute_db(
        "UPDATE Plants SET PlantName = ?, Description = ? WHERE PlantID = ?",
        (payload["plant_name"], payload.get("description"), plant_id),
    )
    return jsonify({"message": "पीक अपडेट झाले."})


@admin_bp.route("/delete-plant/<int:plant_id>", methods=["DELETE"])
@admin_login_required
def delete_plant(plant_id: int):
    execute_db("DELETE FROM Plants WHERE PlantID = ?", (plant_id,))
    return jsonify({"message": "पीक हटवले."})


@admin_bp.route("/diseases", methods=["GET"])
@admin_login_required
def diseases():
    rows = query_db(
        """
        SELECT d.*, p.PlantName
        FROM Diseases d
        JOIN Plants p ON p.PlantID = d.PlantID
        ORDER BY p.PlantName, d.DiseaseName
        """
    )
    diseases_data = [dict(row) for row in rows]
    plants = query_db("SELECT * FROM Plants ORDER BY PlantName")
    if _wants_json():
        return jsonify(diseases_data)
    return render_template("admin/diseases.html", diseases=diseases_data, plants=plants)


@admin_bp.route("/add-disease", methods=["POST"])
@admin_login_required
def add_disease():
    payload = request.get_json(silent=True) or request.form
    disease_id = execute_db(
        """
        INSERT INTO Diseases (PlantID, DiseaseName, Symptoms, Treatment, Supplement, Notes)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            payload["plant_id"],
            payload["disease_name"],
            payload.get("symptoms"),
            payload.get("treatment"),
            payload.get("supplement"),
            payload.get("notes"),
        ),
    )
    if _wants_json():
        return jsonify({"message": "रोग जोडला.", "disease_id": disease_id}), 201
    flash("रोग यशस्वीरीत्या जोडला.", "success")
    return redirect(url_for("admin.diseases"))


@admin_bp.route("/update-disease/<int:disease_id>", methods=["PUT", "POST"])
@admin_login_required
def update_disease(disease_id: int):
    payload = request.get_json(silent=True) or request.form
    execute_db(
        """
        UPDATE Diseases
        SET PlantID = ?, DiseaseName = ?, Symptoms = ?, Treatment = ?, Supplement = ?, Notes = ?
        WHERE DiseaseID = ?
        """,
        (
            payload["plant_id"],
            payload["disease_name"],
            payload.get("symptoms"),
            payload.get("treatment"),
            payload.get("supplement"),
            payload.get("notes"),
            disease_id,
        ),
    )
    return jsonify({"message": "रोग अपडेट झाला."})


@admin_bp.route("/delete-disease/<int:disease_id>", methods=["DELETE"])
@admin_login_required
def delete_disease(disease_id: int):
    execute_db("DELETE FROM Diseases WHERE DiseaseID = ?", (disease_id,))
    return jsonify({"message": "रोग हटवला."})


@admin_bp.route("/dataset")
@admin_login_required
def dataset_page():
    sync_result = _ensure_seed_dataset_available(notify=True)
    plants = query_db("SELECT * FROM Plants ORDER BY PlantName")
    diseases = query_db(
        """
        SELECT d.DiseaseID, d.DiseaseName, d.PlantID, p.PlantName
        FROM Diseases d
        JOIN Plants p ON p.PlantID = d.PlantID
        ORDER BY p.PlantName, d.DiseaseName
        """
    )
    statistics = DatasetService.get_dataset_statistics()
    return render_template(
        "admin/dataset.html",
        plants=plants,
        diseases=diseases,
        statistics=statistics,
        sync_result=sync_result,
    )


@admin_bp.route("/upload-dataset-image", methods=["POST"])
@admin_login_required
def upload_dataset_image():
    try:
        result = DatasetService.add_custom_image(
            request.files.get("dataset_image"),
            request.form.get("plant_id", type=int),
            request.form.get("disease_id", type=int),
        )
        if _wants_json():
            return jsonify({"message": "डेटासेट फोटो अपलोड झाला.", "result": result})
        flash("डेटासेट फोटो यशस्वीरीत्या अपलोड झाला.", "success")
    except Exception as exc:  # noqa: BLE001
        if _wants_json():
            return jsonify({"error": str(exc)}), 400
        flash(str(exc), "danger")
    return redirect(url_for("admin.dataset_page"))


@admin_bp.route("/dataset-images/<int:image_id>", methods=["DELETE"])
@admin_login_required
def delete_dataset_image(image_id: int):
    DatasetService.delete_dataset_image(image_id)
    return jsonify({"message": "डेटासेट फोटो हटवला."})


@admin_bp.route("/import-plantvillage", methods=["POST"])
@admin_login_required
def import_plantvillage():
    payload = request.get_json(silent=True) or request.form
    try:
        result = DatasetService.import_plantvillage(payload["source_dir"])
        return jsonify({"message": "PlantVillage आयात पूर्ण झाले.", "result": result})
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": str(exc)}), 400


@admin_bp.route("/sync-seed-dataset", methods=["POST"])
@admin_login_required
def sync_seed_dataset():
    payload = request.get_json(silent=True) or request.form
    try:
        source_dir = payload.get("source_dir")
        result = (
            DatasetService.sync_existing_seed_dataset(source_dir)
            if source_dir
            else DatasetService.ensure_seed_dataset_registered()
        )
        return jsonify({"message": "सीड डेटासेट सिंक झाले.", "result": result})
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": str(exc)}), 400


@admin_bp.route("/generate-dataset", methods=["POST"])
@admin_login_required
def generate_dataset():
    try:
        _ensure_seed_dataset_available()
        summary = DatasetService.rebuild_merged_dataset()
        return jsonify({"message": "ट्रेनिंग डेटासेट तयार झाले.", "summary": summary.__dict__})
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": str(exc)}), 400


@admin_bp.route("/training")
@admin_login_required
def training_page():
    _ensure_seed_dataset_available(notify=True)
    runs = query_db("SELECT * FROM TrainingRuns ORDER BY TrainingDate DESC")
    status = TrainingService.current_status()
    return render_template("admin/training.html", runs=runs, status=status)


@admin_bp.route("/train-model", methods=["POST"])
@admin_login_required
def train_model():
    _ensure_seed_dataset_available()
    result = TrainingService.start_async_training()
    status_code = 202 if result["started"] else 409
    return jsonify(result), status_code


@admin_bp.route("/training-status")
@admin_login_required
def training_status():
    return jsonify(TrainingService.current_status())


@admin_bp.route("/training-runs")
@admin_login_required
def training_runs():
    rows = query_db("SELECT * FROM TrainingRuns ORDER BY TrainingDate DESC")
    payload = [dict(row) for row in rows]
    if _wants_json():
        return jsonify(payload)
    return render_template("admin/training.html", runs=rows, status=TrainingService.current_status())


@admin_bp.route("/statistics")
@admin_login_required
def statistics():
    payload = AnalyticsService.statistics_payload()
    if _wants_json():
        return jsonify(payload)
    return render_template("admin/statistics.html", chart_data=payload)
