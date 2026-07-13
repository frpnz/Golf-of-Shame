#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from common import connect, ensure_schema, update_match


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Aggiorna una partita esistente nel DB SQLite")
    parser.add_argument("--db", required=True, help="Percorso del database SQLite")
    parser.add_argument("--input", required=True, help="JSON partita modificato")
    group = parser.add_mutually_exclusive_group(required=False)
    group.add_argument("--id", type=int, dest="match_id", help="ID numerico della partita da aggiornare")
    group.add_argument("--import-key", help="import_key della partita da aggiornare")
    parser.add_argument("--export-docs", default="", help="Rigenera stats JSON nella cartella docs dopo l'aggiornamento")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    conn = connect(args.db)
    ensure_schema(conn)
    try:
        match_id = update_match(conn, payload, match_id=args.match_id, import_key=args.import_key)
    except ValueError as exc:
        print(f"Errore: {exc}", file=sys.stderr)
        return 1

    print(f"Partita aggiornata con id={match_id}")
    if args.export_docs:
        cmd = [sys.executable, str(Path(__file__).with_name("export_stats.py")), "--db", args.db, "--docs", args.export_docs]
        subprocess.check_call(cmd)
        print(f"Stats rigenerate in {args.export_docs}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
