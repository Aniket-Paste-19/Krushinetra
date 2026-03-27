from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Iterable

from flask import current_app, g


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        db_path = Path(current_app.config["DATABASE_PATH"])
        connection = sqlite3.connect(db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        g.db = connection
    return g.db


def close_db(_error: Exception | None = None) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()


def query_db(
    query: str,
    args: Iterable[Any] | None = None,
    *,
    one: bool = False,
) -> sqlite3.Row | list[sqlite3.Row] | None:
    cursor = get_db().execute(query, tuple(args or ()))
    rows = cursor.fetchall()
    cursor.close()
    if one:
        return rows[0] if rows else None
    return rows


def execute_db(query: str, args: Iterable[Any] | None = None) -> int:
    db = get_db()
    cursor = db.execute(query, tuple(args or ()))
    db.commit()
    lastrowid = cursor.lastrowid
    cursor.close()
    return lastrowid


def executemany_db(query: str, args: Iterable[Iterable[Any]]) -> None:
    db = get_db()
    db.executemany(query, args)
    db.commit()


def init_app(app) -> None:
    app.teardown_appcontext(close_db)
