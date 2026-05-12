#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from common import connect, ensure_schema, rename_players


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Rinomina tutte le occorrenze di un player nel database SQLite."
    )
    parser.add_argument("--db", default="data/golf_tracker.sqlite", help="Percorso al database SQLite")
    parser.add_argument("--from", dest="old_name", required=True, help="Nome player attuale da cercare")
    parser.add_argument("--to", dest="new_name", required=True, help="Nuovo nome player")
    parser.add_argument(
        "--case-insensitive",
        action="store_true",
        help="Cerca il nome ignorando maiuscole/minuscole",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Mostra i player che verrebbero rinominati senza modificare il DB",
    )
    parser.add_argument(
        "--export-docs",
        help="Se indicato, rigenera i file statici dentro questa cartella, es. docs",
    )
    args = parser.parse_args()

    conn = connect(args.db)
    ensure_schema(conn)
    result = rename_players(
        conn,
        old_name=args.old_name,
        new_name=args.new_name,
        case_sensitive=not args.case_insensitive,
        dry_run=args.dry_run,
    )

    if result.get("blocked"):
        print(f"Rinomina bloccata: trovate {result['matched_players']} occorrenze player da '{result['old_name']}' a '{result['new_name']}', ma ci sono conflitti.")
    else:
        action = "Trovate" if args.dry_run else "Rinominate"
        print(f"{action} {result['matched_players']} occorrenze player da '{result['old_name']}' a '{result['new_name']}'.")

    if result["matches"]:
        print("Match coinvolti:")
        for item in result["matches"]:
            course = item["course"] or "campo n/d"
            team = item["team_name"] or "side senza nome"
            print(f"- match #{item['match_id']} | {item['played_at']} | {course} | {team}")
    else:
        print("Nessun player corrispondente trovato.")

    if result.get("conflicts"):
        print("\nConflitti rilevati:")
        for item in result["conflicts"]:
            course = item["course"] or "campo n/d"
            print(
                f"- match #{item['match_id']} | {item['played_at']} | {course}: "
                f"'{item['new_player_name']}' e gia presente"
            )
        if not args.dry_run:
            return 1

    if args.export_docs and not args.dry_run:
        import subprocess
        import sys

        cmd = [
            sys.executable,
            str(Path(__file__).with_name("export_stats.py")),
            "--db",
            args.db,
            "--docs",
            args.export_docs,
        ]
        subprocess.check_call(cmd)
        print(f"Statistiche rigenerate in {args.export_docs}")
    elif args.export_docs and args.dry_run:
        print("Dry-run: statistiche non rigenerate.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
