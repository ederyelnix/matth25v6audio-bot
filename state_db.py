"""
DB locale du bot (bot_state.db), séparée des DB officielles.
Structure actée avec l'utilisateur :
  - users(telegram_user_id, ui_language, created_at, updated_at)
  - published_sermons(language, number, source_updated_at, message_id, published_at)
"""
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    telegram_user_id INTEGER PRIMARY KEY,
    ui_language      TEXT NOT NULL,
    created_at       TEXT NOT NULL,
    updated_at       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS published_sermons (
    language           TEXT NOT NULL,
    number             INTEGER NOT NULL,
    source_updated_at  TEXT,
    message_id         INTEGER NOT NULL,
    published_at       TEXT NOT NULL,
    PRIMARY KEY (language, number)
);

CREATE TABLE IF NOT EXISTS db_updates_known (
    langue      TEXT PRIMARY KEY,
    updated_at  TEXT NOT NULL
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def _connect():
    conn = sqlite3.connect(config.STATE_DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with _connect() as conn:
        conn.executescript(SCHEMA)


# ---------------------------------------------------------------------------
# users
# ---------------------------------------------------------------------------
def set_user_language(telegram_user_id: int, ui_language: str):
    now = _now()
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO users (telegram_user_id, ui_language, created_at, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(telegram_user_id) DO UPDATE SET
                ui_language = excluded.ui_language,
                updated_at = excluded.updated_at
            """,
            (telegram_user_id, ui_language, now, now),
        )


def get_user_language(telegram_user_id: int) -> Optional[str]:
    with _connect() as conn:
        row = conn.execute(
            "SELECT ui_language FROM users WHERE telegram_user_id = ?",
            (telegram_user_id,),
        ).fetchone()
        return row["ui_language"] if row else None


# ---------------------------------------------------------------------------
# published_sermons
# ---------------------------------------------------------------------------
@dataclass
class PublishedSermon:
    language: str
    number: int
    source_updated_at: Optional[str]
    message_id: int
    published_at: str


def get_published(language: str, number: int) -> Optional[PublishedSermon]:
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM published_sermons WHERE language = ? AND number = ?",
            (language, number),
        ).fetchone()
        if not row:
            return None
        return PublishedSermon(**dict(row))


def get_all_published(language: str) -> dict:
    """Retourne {number: PublishedSermon} pour une langue, pour comparaison en masse."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM published_sermons WHERE language = ?",
            (language,),
        ).fetchall()
        return {r["number"]: PublishedSermon(**dict(r)) for r in rows}


def upsert_published(language: str, number: int, source_updated_at: str, message_id: int):
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO published_sermons (language, number, source_updated_at, message_id, published_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(language, number) DO UPDATE SET
                source_updated_at = excluded.source_updated_at,
                message_id = excluded.message_id,
                published_at = excluded.published_at
            """,
            (language, number, source_updated_at, message_id, _now()),
        )


def import_raw_entry(language: str, number: int, message_id: int, published_at: str):
    """
    Utilisé uniquement par le script d'import initial (historique canal FR).
    source_updated_at reste NULL volontairement : on ne sait pas si le fichier
    déjà publié correspond à l'état actuel de la DB, donc le prochain cycle de
    sync le retraitera automatiquement comme "à mettre à jour".
    """
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO published_sermons (language, number, source_updated_at, message_id, published_at)
            VALUES (?, ?, NULL, ?, ?)
            ON CONFLICT(language, number) DO UPDATE SET
                message_id = excluded.message_id,
                published_at = excluded.published_at
            """,
            (language, number, message_id, published_at),
        )


# ---------------------------------------------------------------------------
# db_updates_known — dernière date de mise à jour connue par langue (et 'common'),
# renvoyée par l'endpoint léger all-new-updates. Remplace l'ancien mécanisme qui
# téléchargeait tout common.db à chaque cycle juste pour comparer des dates.
# ---------------------------------------------------------------------------
def get_all_known_updates() -> dict:
    """Retourne {langue: updated_at} pour 'common' + chaque code langue interne."""
    with _connect() as conn:
        rows = conn.execute("SELECT langue, updated_at FROM db_updates_known").fetchall()
        return {r["langue"]: r["updated_at"] for r in rows}


def set_known_update(langue: str, updated_at: str):
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO db_updates_known (langue, updated_at)
            VALUES (?, ?)
            ON CONFLICT(langue) DO UPDATE SET updated_at = excluded.updated_at
            """,
            (langue, updated_at),
        )
