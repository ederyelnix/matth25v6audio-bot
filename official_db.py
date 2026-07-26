"""
Accès en LECTURE SEULE aux DB officielles (matth25v6_XX.db).
Les colonnes utilisées ici correspondent exactement à ce qui est vérifié
dans matth25v6_db.cpp / .h (aucune supposition).

La vérification des mises à jour (ex common.db / langue_last_updateds) passe
maintenant par l'endpoint léger all-new-updates (voir db_downloader.fetch_all_updates),
donc plus besoin de lire common.db ici.
"""
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import List

import config


def _connect_ro(db_path: Path) -> sqlite3.Connection:
    uri = f"file:{db_path}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


# ---------------------------------------------------------------------------
# matth25v6_XX.db — table sermons
# ---------------------------------------------------------------------------
@dataclass
class Sermon:
    id: int
    number: int
    title: str
    audio: str
    audio_name: str
    publication_date: str
    updated_at: str


def get_all_sermons(lang_db_path: Path) -> List[Sermon]:
    """
    Réplique Sermon_GetAll : colonnes vérifiées dans le .cpp.
    On ne sélectionne que celles dont le bot a réellement besoin.
    """
    conn = _connect_ro(lang_db_path)
    try:
        rows = conn.execute(
            """
            SELECT id, number, title, audio, audio_name, publication_date, updated_at
            FROM sermons
            WHERE is_active = 1
            ORDER BY number ASC
            """
        ).fetchall()
        return [
            Sermon(
                id=r["id"],
                number=r["number"],
                title=r["title"],
                audio=r["audio"],
                audio_name=r["audio_name"],
                publication_date=r["publication_date"],
                updated_at=r["updated_at"],
            )
            for r in rows
        ]
    finally:
        conn.close()


def get_sermon_count(lang_db_path: Path) -> int:
    conn = _connect_ro(lang_db_path)
    try:
        row = conn.execute("SELECT COUNT(*) AS c FROM sermons WHERE is_active = 1").fetchone()
        return row["c"]
    finally:
        conn.close()


def get_sermon_by_number(lang_db_path: Path, number: int) -> "Sermon | None":
    conn = _connect_ro(lang_db_path)
    try:
        r = conn.execute(
            """
            SELECT id, number, title, audio, audio_name, publication_date, updated_at
            FROM sermons
            WHERE is_active = 1 AND number = ?
            """,
            (number,),
        ).fetchone()
        if r is None:
            return None
        return Sermon(
            id=r["id"], number=r["number"], title=r["title"], audio=r["audio"],
            audio_name=r["audio_name"], publication_date=r["publication_date"], updated_at=r["updated_at"],
        )
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# matth25v6_XX.db — table verses (liée à sermons par sermon_id)
# ---------------------------------------------------------------------------
@dataclass
class Verse:
    number: int
    content: str


def get_verses_for_sermon(lang_db_path: Path, sermon_number: int) -> List[Verse]:
    """
    Réplique SQL_VERSE du .cpp (jointure verses/sermons sur sermon_id),
    versets dans l'ordre.
    """
    conn = _connect_ro(lang_db_path)
    try:
        rows = conn.execute(
            """
            SELECT v.number, v.content
            FROM verses v
            INNER JOIN sermons s ON s.id = v.sermon_id
            WHERE s.number = ?
            ORDER BY v.number ASC
            """,
            (sermon_number,),
        ).fetchall()
        return [Verse(number=r["number"], content=r["content"]) for r in rows]
    finally:
        conn.close()
