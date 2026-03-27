from __future__ import annotations

from functools import wraps

from flask import flash, redirect, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from backend.database import execute_db, query_db


def register_farmer(name: str, email: str, password: str, phone: str | None = None) -> int:
    return execute_db(
        """
        INSERT INTO Farmers (Name, Email, PasswordHash, Phone)
        VALUES (?, ?, ?, ?)
        """,
        (name.strip(), email.strip().lower(), generate_password_hash(password), phone),
    )


def authenticate_farmer(email: str, password: str):
    farmer = query_db(
        "SELECT * FROM Farmers WHERE Email = ?",
        (email.strip().lower(),),
        one=True,
    )
    if not farmer:
        return None
    if farmer["Status"] != "active":
        return "blocked"
    if check_password_hash(farmer["PasswordHash"], password):
        execute_db(
            "UPDATE Farmers SET LastLogin = CURRENT_TIMESTAMP WHERE FarmerID = ?",
            (farmer["FarmerID"],),
        )
        return query_db(
            "SELECT * FROM Farmers WHERE FarmerID = ?",
            (farmer["FarmerID"],),
            one=True,
        )
    return None


def authenticate_admin(username: str, password: str):
    admin = query_db(
        "SELECT * FROM AdminUsers WHERE Username = ?",
        (username.strip(),),
        one=True,
    )
    if admin and check_password_hash(admin["PasswordHash"], password):
        return admin
    return None


def farmer_login_required(view):
    @wraps(view)
    def wrapped_view(**kwargs):
        if not session.get("farmer_id"):
            if request.path.startswith("/api/"):
                return {"error": "लॉगिन आवश्यक आहे."}, 401
            flash("पुढे जाण्यासाठी कृपया लॉगिन करा.", "warning")
            return redirect(url_for("farmer.login_page"))
        return view(**kwargs)

    return wrapped_view


def admin_login_required(view):
    @wraps(view)
    def wrapped_view(**kwargs):
        if not session.get("admin_id"):
            wants_json = request.is_json or request.args.get("format") == "json"
            if wants_json:
                return {"error": "अॅडमिन लॉगिन आवश्यक आहे."}, 401
            flash("कृपया अॅडमिन म्हणून लॉगिन करा.", "warning")
            return redirect(url_for("admin.login_page"))
        return view(**kwargs)

    return wrapped_view
