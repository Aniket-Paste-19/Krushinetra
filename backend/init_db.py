from __future__ import annotations

import sys
from pathlib import Path

from flask import Flask
from werkzeug.security import generate_password_hash

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from backend.config import Config
from backend.database import get_db, init_app


def init_database(app: Flask) -> None:
    schema_path = Path(app.config["BACKEND_DIR"]) / "schema.sql"
    with app.app_context():
        db = get_db()
        db.executescript(schema_path.read_text(encoding="utf-8"))
        db.execute(
            """
            INSERT INTO AdminUsers (Username, PasswordHash)
            VALUES (?, ?)
            """,
            (
                app.config["DEFAULT_ADMIN_USERNAME"],
                generate_password_hash(app.config["DEFAULT_ADMIN_PASSWORD"]),
            ),
        )
        db.commit()


def build_app() -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)
    Config.ensure_directories()
    init_app(app)
    return app


if __name__ == "__main__":
    app = build_app()
    init_database(app)
    print("Database initialized successfully.")
