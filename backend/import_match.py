#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from common import connect, ensure_schema, insert_match


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Importa una partita JSON nel DB")
    parser.add_argument("--db", required=True)
    parser.add_argument("--input", required=True)
    parser.add_argument("--export-docs", default="")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    conn = connect(args.db)
    ensure_schema(conn)
    match_id, inserted = insert_match(conn, payload)
    if inserted:
        print(f"Partita importata con id={match_id}")
    else:
        print(f"Partita già presente nel DB con id={match_id} (stesso import_key)")
    if args.export_docs:
        cmd = [sys.executable, str(Path(__file__).with_name("export_stats.py")), "--db", args.db, "--docs", args.export_docs]
        subprocess.check_call(cmd)
        print(f"Stats rigenerate in {args.export_docs}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
