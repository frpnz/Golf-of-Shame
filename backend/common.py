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

CREATE TABLE IF NOT EXISTS match_tag (
  match_id INTEGER NOT NULL,
  tag TEXT NOT NULL,
  PRIMARY KEY (match_id, tag),
  FOREIGN KEY (match_id) REFERENCES match(id) ON DELETE CASCADE
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


def normalize_tags(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        raw_items = [item.strip() for item in value.split(",")]
    elif isinstance(value, list):
        raw_items = []
        for item in value:
            if isinstance(item, str):
                raw_items.extend(part.strip() for part in item.split(","))
            elif item is not None:
                raw_items.append(str(item).strip())
    else:
        raise ValueError("tags deve essere una lista di stringhe, una stringa separata da virgole o null")

    tags: List[str] = []
    seen = set()
    for item in raw_items:
        tag = " ".join(item.split())
        if not tag:
            continue
        key = tag.casefold()
        if key not in seen:
            seen.add(key)
            tags.append(tag)
    return tags


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

    if winners < 1:
        raise ValueError("Serve almeno 1 side con punto/vittoria. Per un pareggio, marca piu side come vincenti")

    holes = payload.get("holes")
    if holes is not None:
        try:
            holes = int(holes)
        except (TypeError, ValueError):
            raise ValueError("holes deve essere un intero o null") from None

    tags_value = payload.get("tags", payload.get("tag"))
    tags = normalize_tags(tags_value)

    return {
        "version": payload.get("version", "golf-match.v1"),
        "played_at": played_at.strip(),
        "course": (payload.get("course") or "").strip() or None,
        "holes": holes,
        "notes": (payload.get("notes") or "").strip() or None,
        "tags": tags,
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
    for tag in clean.get("tags", []):
        conn.execute(
            "INSERT OR IGNORE INTO match_tag (match_id, tag) VALUES (?, ?)",
            (match_id, tag),
        )

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


def delete_match(conn: sqlite3.Connection, *, match_id: int | None = None, import_key: str | None = None) -> bool:
    if match_id is None and not import_key:
        raise ValueError("Specificare match_id oppure import_key")
    if match_id is not None and import_key:
        raise ValueError("Specificare solo uno tra match_id e import_key")

    if match_id is not None:
        cur = conn.execute("DELETE FROM match WHERE id = ?", (match_id,))
    else:
        cur = conn.execute("DELETE FROM match WHERE import_key = ?", (import_key,))
    conn.commit()
    return cur.rowcount > 0


def rename_sides(
    conn: sqlite3.Connection,
    *,
    old_name: str,
    new_name: str,
    case_sensitive: bool = True,
    dry_run: bool = False,
) -> Dict[str, Any]:
    old_name = str(old_name or "").strip()
    new_name = str(new_name or "").strip()
    if not old_name:
        raise ValueError("Il nome side/team da cercare e obbligatorio")
    if not new_name:
        raise ValueError("Il nuovo nome side/team e obbligatorio")
    if old_name == new_name:
        raise ValueError("Il nuovo nome deve essere diverso dal nome attuale")

    if case_sensitive:
        where_sql = "team_name = ?"
        params: tuple[Any, ...] = (old_name,)
    else:
        where_sql = "LOWER(team_name) = LOWER(?)"
        params = (old_name,)

    rows = conn.execute(
        f"""
        SELECT
          s.id AS side_id,
          s.team_name AS old_team_name,
          m.id AS match_id,
          m.played_at,
          m.course
        FROM match_side s
        JOIN match m ON m.id = s.match_id
        WHERE {where_sql}
        ORDER BY m.played_at DESC, m.id DESC, s.side_order ASC, s.id ASC
        """,
        params,
    ).fetchall()

    affected = [
        {
            "side_id": int(row["side_id"]),
            "match_id": int(row["match_id"]),
            "played_at": row["played_at"],
            "course": row["course"],
            "old_team_name": row["old_team_name"],
            "new_team_name": new_name,
        }
        for row in rows
    ]

    if affected and not dry_run:
        conn.execute(f"UPDATE match_side SET team_name = ? WHERE {where_sql}", (new_name, *params))
        conn.commit()

    return {
        "old_name": old_name,
        "new_name": new_name,
        "case_sensitive": case_sensitive,
        "dry_run": dry_run,
        "updated_sides": 0 if dry_run else len(affected),
        "matched_sides": len(affected),
        "affected_matches": sorted({item["match_id"] for item in affected}),
        "matches": affected,
    }


def rename_players(
    conn: sqlite3.Connection,
    *,
    old_name: str,
    new_name: str,
    case_sensitive: bool = True,
    dry_run: bool = False,
) -> Dict[str, Any]:
    old_name = str(old_name or "").strip()
    new_name = str(new_name or "").strip()
    if not old_name:
        raise ValueError("Il nome player da cercare e obbligatorio")
    if not new_name:
        raise ValueError("Il nuovo nome player e obbligatorio")
    if old_name == new_name:
        raise ValueError("Il nuovo nome deve essere diverso dal nome attuale")

    if case_sensitive:
        where_sql = "p.player_name = ?"
        conflict_sql = "p2.player_name = ?"
        params: tuple[Any, ...] = (old_name,)
        conflict_param = new_name
    else:
        where_sql = "LOWER(p.player_name) = LOWER(?)"
        conflict_sql = "LOWER(p2.player_name) = LOWER(?)"
        params = (old_name,)
        conflict_param = new_name

    rows = conn.execute(
        f"""
        SELECT
          p.id AS player_row_id,
          p.side_id,
          p.player_name AS old_player_name,
          s.team_name,
          m.id AS match_id,
          m.played_at,
          m.course
        FROM match_player p
        JOIN match_side s ON s.id = p.side_id
        JOIN match m ON m.id = s.match_id
        WHERE {where_sql}
        ORDER BY m.played_at DESC, m.id DESC, s.side_order ASC, p.id ASC
        """,
        params,
    ).fetchall()

    affected = [
        {
            "player_row_id": int(row["player_row_id"]),
            "side_id": int(row["side_id"]),
            "match_id": int(row["match_id"]),
            "played_at": row["played_at"],
            "course": row["course"],
            "team_name": row["team_name"],
            "old_player_name": row["old_player_name"],
            "new_player_name": new_name,
        }
        for row in rows
    ]

    conflicts = []
    for item in affected:
        conflict = conn.execute(
            f"""
            SELECT p2.id, p2.player_name
            FROM match_player p2
            JOIN match_side s2 ON s2.id = p2.side_id
            WHERE s2.match_id = ?
              AND p2.id <> ?
              AND {conflict_sql}
            LIMIT 1
            """,
            (item["match_id"], item["player_row_id"], conflict_param),
        ).fetchone()
        if conflict is not None:
            conflicts.append({
                "match_id": item["match_id"],
                "played_at": item["played_at"],
                "course": item["course"],
                "old_player_name": item["old_player_name"],
                "new_player_name": new_name,
                "existing_player_name": conflict["player_name"],
            })

    blocked = bool(conflicts) and not dry_run

    if affected and not dry_run and not blocked:
        conn.execute(f"UPDATE match_player AS p SET player_name = ? WHERE {where_sql}", (new_name, *params))
        conn.commit()

    return {
        "old_name": old_name,
        "new_name": new_name,
        "case_sensitive": case_sensitive,
        "dry_run": dry_run,
        "updated_players": 0 if dry_run or blocked else len(affected),
        "matched_players": len(affected),
        "blocked": blocked,
        "affected_matches": sorted({item["match_id"] for item in affected}),
        "matches": affected,
        "conflicts": conflicts,
    }


def fetch_matches(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    matches = []
    match_rows = conn.execute(
        "SELECT id, played_at, course, holes, notes, import_key FROM match ORDER BY played_at DESC, id DESC"
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
        tags = [
            trow["tag"]
            for trow in conn.execute(
                "SELECT tag FROM match_tag WHERE match_id = ? ORDER BY tag COLLATE NOCASE ASC",
                (row["id"],),
            ).fetchall()
        ]
        matches.append({
            "id": row["id"],
            "played_at": row["played_at"],
            "course": row["course"],
            "holes": row["holes"],
            "notes": row["notes"],
            "import_key": row["import_key"],
            "tags": tags,
            "is_draw": sum(1 for side in sides if side["is_winner"]) > 1,
            "sides": sides,
        })
    return matches
