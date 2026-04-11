#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List

SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS match (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  played_at TEXT NOT NULL,
  course TEXT,
  holes INTEGER,
  notes TEXT,
  import_key TEXT NOT NULL UNIQUE,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS match_side (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  match_id INTEGER NOT NULL,
  side_order INTEGER NOT NULL,
  team_name TEXT,
  is_winner INTEGER NOT NULL CHECK (is_winner IN (0, 1)),
  FOREIGN KEY (match_id) REFERENCES match(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS match_player (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  side_id INTEGER NOT NULL,
  player_name TEXT NOT NULL,
  FOREIGN KEY (side_id) REFERENCES match_side(id) ON DELETE CASCADE
);
"""


def connect(db_path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_SQL)
    conn.commit()


def canonical_import_key(payload: Dict[str, Any]) -> str:
    normalized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def validate_match_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("Il JSON deve essere un oggetto")

    played_at = payload.get("played_at")
    if not isinstance(played_at, str) or not played_at.strip():
        raise ValueError("played_at è obbligatorio")

    sides = payload.get("sides")
    if not isinstance(sides, list) or len(sides) < 2:
        raise ValueError("Servono almeno 2 side")

    winners = 0
    seen_players = set()
    clean_sides: List[Dict[str, Any]] = []
    for idx, side in enumerate(sides, start=1):
        if not isinstance(side, dict):
            raise ValueError(f"Side {idx} non valido")
        players = side.get("players")
        if not isinstance(players, list) or not players:
            raise ValueError(f"Side {idx}: players obbligatorio")
        clean_players = []
        for player in players:
            if not isinstance(player, str) or not player.strip():
                raise ValueError(f"Side {idx}: player non valido")
            name = player.strip()
            if name in seen_players:
                raise ValueError(f"Player duplicato nella partita: {name}")
            seen_players.add(name)
            clean_players.append(name)
        is_winner = bool(side.get("is_winner", False))
        winners += 1 if is_winner else 0
        team_name = side.get("team_name")
        if team_name is not None:
            team_name = str(team_name).strip() or None
        if not team_name:
            team_name = "-".join(clean_players)
        clean_sides.append({
            "team_name": team_name,
            "is_winner": is_winner,
            "players": clean_players,
        })

    if winners != 1:
        raise ValueError("Deve esserci esattamente 1 side vincente")

    holes = payload.get("holes")
    if holes is not None:
        try:
            holes = int(holes)
        except (TypeError, ValueError):
            raise ValueError("holes deve essere un intero o null") from None

    return {
        "version": payload.get("version", "golf-match.v1"),
        "played_at": played_at.strip(),
        "course": (payload.get("course") or "").strip() or None,
        "holes": holes,
        "notes": (payload.get("notes") or "").strip() or None,
        "sides": clean_sides,
    }


def find_match_by_import_key(conn: sqlite3.Connection, import_key: str) -> int | None:
    row = conn.execute("SELECT id FROM match WHERE import_key = ?", (import_key,)).fetchone()
    return None if row is None else int(row[0])


def insert_match(conn: sqlite3.Connection, payload: Dict[str, Any]) -> tuple[int, bool]:
    clean = validate_match_payload(payload)
    import_key = str(payload.get("import_key") or canonical_import_key(clean)).strip()
    existing_id = find_match_by_import_key(conn, import_key)
    if existing_id is not None:
        return existing_id, False

    cur = conn.execute(
        "INSERT INTO match (played_at, course, holes, notes, import_key) VALUES (?, ?, ?, ?, ?)",
        (clean["played_at"], clean["course"], clean["holes"], clean["notes"], import_key),
    )
    match_id = int(cur.lastrowid)
    for idx, side in enumerate(clean["sides"], start=1):
        cur = conn.execute(
            "INSERT INTO match_side (match_id, side_order, team_name, is_winner) VALUES (?, ?, ?, ?)",
            (match_id, idx, side["team_name"], 1 if side["is_winner"] else 0),
        )
        side_id = int(cur.lastrowid)
        for player in side["players"]:
            conn.execute(
                "INSERT INTO match_player (side_id, player_name) VALUES (?, ?)",
                (side_id, player),
            )
    conn.commit()
    return match_id, True


def fetch_matches(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    matches = []
    match_rows = conn.execute(
        "SELECT id, played_at, course, holes, notes FROM match ORDER BY played_at DESC, id DESC"
    ).fetchall()
    for row in match_rows:
        sides = []
        side_rows = conn.execute(
            "SELECT id, side_order, team_name, is_winner FROM match_side WHERE match_id = ? ORDER BY side_order ASC, id ASC",
            (row["id"],),
        ).fetchall()
        for srow in side_rows:
            players = [
                prow["player_name"]
                for prow in conn.execute(
                    "SELECT player_name FROM match_player WHERE side_id = ? ORDER BY player_name ASC",
                    (srow["id"],),
                ).fetchall()
            ]
            sides.append({
                "team_name": srow["team_name"] or "-".join(players),
                "is_winner": bool(srow["is_winner"]),
                "players": players,
            })
        matches.append({
            "id": row["id"],
            "played_at": row["played_at"],
            "course": row["course"],
            "holes": row["holes"],
            "notes": row["notes"],
            "sides": sides,
        })
    return matches
