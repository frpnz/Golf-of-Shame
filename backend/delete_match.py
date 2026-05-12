#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from common import connect, delete_match, ensure_schema


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Elimina una partita dal DB SQLite")
    parser.add_argument("--db", required=True, help="Percorso del database SQLite")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--id", type=int, dest="match_id", help="ID numerico della partita da eliminare")
    group.add_argument("--import-key", help="import_key della partita da eliminare")
    parser.add_argument("--export-docs", default="", help="Rigenera stats JSON nella cartella docs dopo l'eliminazione")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    conn = connect(args.db)
    ensure_schema(conn)
    deleted = delete_match(conn, match_id=args.match_id, import_key=args.import_key)
    if not deleted:
        print("Nessuna partita trovata con il criterio indicato")
        return 1

    print("Partita eliminata")
    if args.export_docs:
        cmd = [sys.executable, str(Path(__file__).with_name("export_stats.py")), "--db", args.db, "--docs", args.export_docs]
        subprocess.check_call(cmd)
        print(f"Stats rigenerate in {args.export_docs}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
