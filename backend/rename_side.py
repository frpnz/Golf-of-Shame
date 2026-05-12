#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from common import connect, ensure_schema, rename_sides


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Rinomina tutte le side/team corrispondenti nel database SQLite."
    )
    parser.add_argument("--db", default="data/golf_tracker.sqlite", help="Percorso al database SQLite")
    parser.add_argument("--from", dest="old_name", required=True, help="Nome side/team attuale da cercare")
    parser.add_argument("--to", dest="new_name", required=True, help="Nuovo nome side/team")
    parser.add_argument(
        "--case-insensitive",
        action="store_true",
        help="Cerca il nome ignorando maiuscole/minuscole",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Mostra le side che verrebbero rinominate senza modificare il DB",
    )
    parser.add_argument(
        "--export-docs",
        help="Se indicato, rigenera i file statici dentro questa cartella, es. docs",
    )
    args = parser.parse_args()

    conn = connect(args.db)
    ensure_schema(conn)
    result = rename_sides(
        conn,
        old_name=args.old_name,
        new_name=args.new_name,
        case_sensitive=not args.case_insensitive,
        dry_run=args.dry_run,
    )

    action = "Trovate" if args.dry_run else "Rinominate"
    print(f"{action} {result['matched_sides']} side/team da '{result['old_name']}' a '{result['new_name']}'.")

    if result["matches"]:
        print("Match coinvolti:")
        for item in result["matches"]:
            course = item["course"] or "campo n/d"
            print(f"- match #{item['match_id']} | {item['played_at']} | {course}")
    else:
        print("Nessuna side/team corrispondente trovata.")

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
