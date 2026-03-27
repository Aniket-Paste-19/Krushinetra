from __future__ import annotations

import base64
import binascii
import sqlite3
from pathlib import Path

from flask import Blueprint, current_app, flash, jsonify, redirect, render_template, request, session, url_for

from backend.database import query_db
from backend.services.analytics_service import AnalyticsService
from backend.services.auth_service import authenticate_farmer, farmer_login_required, register_farmer
from backend.services.prediction_service import PredictionService
from backend.utils.file_utils import ensure_dir, is_allowed_image, unique_file_path

farmer_bp = Blueprint("farmer", __name__)


def _history_for_farmer(farmer_id: int):
    return query_db(
        """
        SELECT sh.*, p.PlantName, d.DiseaseName
        FROM SearchHistory sh
        JOIN Plants p ON p.PlantID = sh.PlantID
        JOIN Diseases d ON d.DiseaseID = sh.DiseaseID
        WHERE sh.FarmerID = ?
        ORDER BY sh.SearchDate DESC
        """,
        (farmer_id,),
    )


def _save_captured_image(data_url: str) -> Path:
    if not data_url or "," not in data_url:
        raise ValueError("कॅमेरा प्रतिमा डेटा अवैध आहे.")

    header, encoded = data_url.split(",", 1)
    if ";base64" not in header:
        raise ValueError("कॅमेरा प्रतिमेचा फॉरमॅट अवैध आहे.")

    mime_type = header.split(":", 1)[-1].split(";", 1)[0].lower()
    suffix = {
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
    }.get(mime_type, ".jpg")

    try:
        payload = base64.b64decode(encoded)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("कॅमेरा प्रतिमा वाचता आली नाही.") from exc

    destination_dir = ensure_dir(current_app.config["FARMER_UPLOAD_FOLDER"])
    destination = unique_file_path(destination_dir, f"camera_capture{suffix}")
    destination.write_bytes(payload)
    return destination


def _save_leaf_image_from_request() -> Path:
    file = request.files.get("leaf_image")
    if file and file.filename:
        if not is_allowed_image(file.filename):
            raise ValueError("समर्थित नसलेला प्रतिमा फॉरमॅट.")
        destination = unique_file_path(current_app.config["FARMER_UPLOAD_FOLDER"], file.filename)
        file.save(destination)
        return destination

    captured_image_data = request.form.get("captured_image_data", "").strip()
    if captured_image_data:
        return _save_captured_image(captured_image_data)

    raise ValueError("कृपया पानाचा फोटो अपलोड करा किंवा कॅमेरातून फोटो घ्या.")


def _guest_search_usage() -> tuple[int, int]:
    limit = current_app.config["GUEST_SEARCH_LIMIT"]
    used = int(session.get("guest_search_count", 0))
    remaining = max(0, limit - used)
    return used, remaining


def _is_demo_ready() -> bool:
    return Path(current_app.config["MODEL_PATH"]).exists() and Path(current_app.config["CLASS_INDICES_PATH"]).exists()


@farmer_bp.route("/home", methods=["GET", "POST"])
def public_home():
    if session.get("admin_id"):
        return redirect(url_for("admin.dashboard"))
    if session.get("farmer_id"):
        return redirect(url_for("farmer.dashboard"))

    plants = query_db("SELECT * FROM Plants ORDER BY PlantName")
    result = None
    search_limit = current_app.config["GUEST_SEARCH_LIMIT"]
    used_searches, remaining_searches = _guest_search_usage()
    limit_reached = remaining_searches == 0
    demo_ready = _is_demo_ready()

    if request.method == "POST":
        selected_plant_id = request.form.get("plant_id", type=int)
        if not demo_ready:
            flash("AI à¤‡à¤‚à¤œà¤¿à¤¨ à¤¸à¤§à¥à¤¯à¤¾ à¤¤à¤¯à¤¾à¤° à¤¨à¤¾à¤¹à¥€. à¤•à¥ƒà¤ªà¤¯à¤¾ à¤¨à¤‚à¤¤à¤° à¤ªà¥à¤¨à¥à¤¹à¤¾ à¤ªà¥à¤°à¤¯à¤¤à¥à¤¨ à¤•à¤°à¤¾.", "warning")
        elif limit_reached:
            flash("à¤—à¥‡à¤¸à¥à¤Ÿ à¤µà¤¾à¤ªà¤°à¤•à¤°à¥à¤¤à¥à¤¯à¤¾à¤‚à¤¸à¤¾à¤ à¥€ 5 à¤®à¥‹à¤«à¤¤ à¤¶à¥‹à¤§ à¤ªà¥‚à¤°à¥à¤£ à¤à¤¾à¤²à¥‡. à¤ªà¥à¤¢à¥‡ à¤µà¤¾à¤ªà¤°à¤£à¥à¤¯à¤¾à¤¸à¤¾à¤ à¥€ à¤¨à¥‹à¤‚à¤¦à¤£à¥€ à¤•à¤°à¤¾.", "warning")
            return redirect(url_for("farmer.register_page"))
        else:
            try:
                destination = _save_leaf_image_from_request()
                result = PredictionService.predict(destination, None, selected_plant_id)
                session["guest_search_count"] = used_searches + 1
                used_searches, remaining_searches = _guest_search_usage()
                limit_reached = remaining_searches == 0
                flash("à¤¡à¥‡à¤®à¥‹ à¤¤à¤ªà¤¾à¤¸à¤£à¥€ à¤¯à¤¶à¤¸à¥à¤µà¥€ à¤à¤¾à¤²à¥€.", "success")
            except Exception as exc:  # noqa: BLE001
                flash(str(exc), "danger")

    return render_template(
        "public_home.html",
        plants=plants,
        result=result,
        demo_ready=demo_ready,
        guest_search_limit=search_limit,
        guest_searches_used=used_searches,
        guest_searches_remaining=remaining_searches,
        guest_limit_reached=limit_reached,
    )


@farmer_bp.route("/register", methods=["GET", "POST"])
def register_page():
    if request.method == "POST":
        try:
            register_farmer(
                request.form["name"],
                request.form["email"],
                request.form["password"],
                request.form.get("phone"),
            )
            flash("नोंदणी यशस्वी झाली. कृपया लॉगिन करा.", "success")
            return redirect(url_for("farmer.login_page"))
        except sqlite3.IntegrityError:
            flash("हा ईमेल आधीच नोंदणीकृत आहे.", "danger")
    return render_template("farmer/register.html")


@farmer_bp.route("/login", methods=["GET", "POST"])
def login_page():
    if request.method == "POST":
        farmer = authenticate_farmer(request.form["email"], request.form["password"])
        if farmer == "blocked":
            flash("तुमचे खाते ब्लॉक केलेले आहे. कृपया अॅडमिनशी संपर्क साधा.", "danger")
        elif farmer:
            session.clear()
            session["farmer_id"] = farmer["FarmerID"]
            session["farmer_name"] = farmer["Name"]
            return redirect(url_for("farmer.dashboard"))
        else:
            flash("चुकीची लॉगिन माहिती.", "danger")
    return render_template("farmer/login.html")


@farmer_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("farmer.login_page"))


@farmer_bp.route("/dashboard")
@farmer_login_required
def dashboard():
    farmer_id = session["farmer_id"]
    plants = query_db("SELECT * FROM Plants ORDER BY PlantName")
    activity = AnalyticsService.farmer_activity(farmer_id)
    recent_history = _history_for_farmer(farmer_id)[:5]
    return render_template(
        "farmer/dashboard.html",
        plants=plants,
        activity=activity,
        recent_history=recent_history,
    )


@farmer_bp.route("/predict", methods=["GET", "POST"])
@farmer_login_required
def predict_page():
    plants = query_db("SELECT * FROM Plants ORDER BY PlantName")
    result = None
    if request.method == "POST":
        selected_plant_id = request.form.get("plant_id", type=int)
        try:
            destination = _save_leaf_image_from_request()
            result = PredictionService.predict(destination, session["farmer_id"], selected_plant_id)
            flash("तपासणी यशस्वीरीत्या पूर्ण झाली.", "success")
        except Exception as exc:  # noqa: BLE001
            flash(str(exc), "danger")
    return render_template("farmer/predict.html", plants=plants, result=result)


@farmer_bp.route("/history")
@farmer_login_required
def history_page():
    history = _history_for_farmer(session["farmer_id"])
    return render_template("farmer/history.html", history=history)


@farmer_bp.route("/profile")
@farmer_login_required
def profile_page():
    farmer = query_db("SELECT * FROM Farmers WHERE FarmerID = ?", (session["farmer_id"],), one=True)
    activity = AnalyticsService.farmer_activity(session["farmer_id"])
    return render_template("farmer/profile.html", farmer=farmer, activity=activity)


@farmer_bp.route("/api/register", methods=["POST"])
def api_register():
    payload = request.get_json(silent=True) or request.form
    try:
        farmer_id = register_farmer(
            payload["name"],
            payload["email"],
            payload["password"],
            payload.get("phone"),
        )
        return jsonify({"message": "नोंदणी यशस्वी झाली.", "farmer_id": farmer_id}), 201
    except sqlite3.IntegrityError:
        return jsonify({"error": "हा ईमेल आधीच नोंदणीकृत आहे."}), 409


@farmer_bp.route("/api/login", methods=["POST"])
def api_login():
    payload = request.get_json(silent=True) or request.form
    farmer = authenticate_farmer(payload["email"], payload["password"])
    if farmer == "blocked":
        return jsonify({"error": "शेतकरी खाते ब्लॉक केलेले आहे."}), 403
    if not farmer:
        return jsonify({"error": "चुकीची लॉगिन माहिती."}), 401

    session.clear()
    session["farmer_id"] = farmer["FarmerID"]
    session["farmer_name"] = farmer["Name"]
    return jsonify(
        {
            "message": "लॉगिन यशस्वी झाले.",
            "farmer": {
                "FarmerID": farmer["FarmerID"],
                "Name": farmer["Name"],
                "Email": farmer["Email"],
            },
        }
    )


@farmer_bp.route("/api/upload-leaf", methods=["POST"])
@farmer_login_required
def api_upload_leaf():
    selected_plant_id = request.form.get("plant_id", type=int)
    try:
        destination = _save_leaf_image_from_request()
        result = PredictionService.predict(destination, session["farmer_id"], selected_plant_id)
        return jsonify(result)
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": str(exc)}), 400


@farmer_bp.route("/api/history")
@farmer_login_required
def api_history():
    rows = _history_for_farmer(session["farmer_id"])
    return jsonify([dict(row) for row in rows])


@farmer_bp.route("/api/profile")
@farmer_login_required
def api_profile():
    farmer = query_db("SELECT * FROM Farmers WHERE FarmerID = ?", (session["farmer_id"],), one=True)
    activity = AnalyticsService.farmer_activity(session["farmer_id"])
    return jsonify({"farmer": dict(farmer), "activity": activity})
