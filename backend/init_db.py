#!/usr/bin/env python3
from __future__ import annotations

import argparse
from common import connect, ensure_schema, insert_match

DEMO_MATCHES = [
    {
        "played_at": "2026-04-01T10:00:00",
        "course": "Golf Club Milano",
        "holes": 18,
        "notes": "Demo 2v2",
        "sides": [
            {"team_name": "Team A", "is_winner": True, "players": ["Mario", "Luca"]},
            {"team_name": "Team B", "is_winner": False, "players": ["Anna", "Paolo"]},
        ],
    },
    {
        "played_at": "2026-04-03T11:00:00",
        "course": "Golf Club Torino",
        "holes": 9,
        "notes": "Demo singolo",
        "sides": [
            {"is_winner": False, "players": ["Mario"]},
            {"is_winner": True, "players": ["Anna"]},
            {"is_winner": False, "players": ["Luca"]},
        ],
    },
    {
        "played_at": "2026-04-05T16:00:00",
        "course": "Golf Club Milano",
        "holes": 18,
        "notes": "Demo 2v1",
        "sides": [
            {"is_winner": True, "players": ["Mario", "Paolo"]},
            {"is_winner": False, "players": ["Anna"]},
        ],
    },
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inizializza il DB SQLite")
    parser.add_argument("--db", required=True, help="Percorso DB SQLite")
    parser.add_argument("--seed-demo", action="store_true", help="Inserisce dati demo")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    conn = connect(args.db)
    ensure_schema(conn)
    if args.seed_demo:
        count = conn.execute("SELECT COUNT(*) FROM match").fetchone()[0]
        if count == 0:
            for payload in DEMO_MATCHES:
                insert_match(conn, payload)
            print(f"Inserite {len(DEMO_MATCHES)} partite demo")
        else:
            print("DB già popolato, seed demo saltato")
    print(f"DB pronto: {args.db}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
