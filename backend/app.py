from __future__ import annotations

from pathlib import Path

from flask import Flask, redirect, session, url_for

from backend.config import Config
from backend.database import init_app as init_db_app
from backend.routes.admin_routes import admin_bp
from backend.routes.farmer_routes import farmer_bp


def create_app() -> Flask:
    app = Flask(
        __name__,
        template_folder=str(Path(__file__).resolve().parent / "templates"),
        static_folder=str(Path(__file__).resolve().parent / "static"),
    )
    app.config.from_object(Config)
    Config.ensure_directories()
    init_db_app(app)

    app.register_blueprint(farmer_bp)
    app.register_blueprint(admin_bp)

    @app.route("/")
    def index():
        if session.get("admin_id"):
            return redirect(url_for("admin.dashboard"))
        if session.get("farmer_id"):
            return redirect(url_for("farmer.dashboard"))
        return redirect(url_for("farmer.public_home"))

    return app


if __name__ == "__main__":
    flask_app = create_app()
    flask_app.run(debug=True)
