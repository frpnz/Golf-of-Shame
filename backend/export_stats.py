#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List

from common import connect, ensure_schema, fetch_matches

MATCH_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "Golf Match Input",
    "type": "object",
    "required": ["played_at", "sides"],
    "properties": {
        "version": {"type": "string"},
        "import_key": {"type": "string"},
        "played_at": {"type": "string"},
        "course": {"type": ["string", "null"]},
        "holes": {"type": ["integer", "null"]},
        "notes": {"type": ["string", "null"]},
        "sides": {
            "type": "array",
            "minItems": 2,
            "items": {
                "type": "object",
                "required": ["players", "is_winner"],
                "properties": {
                    "team_name": {"type": ["string", "null"]},
                    "is_winner": {"type": "boolean"},
                    "players": {
                        "type": "array",
                        "minItems": 1,
                        "items": {"type": "string"}
                    }
                }
            }
        }
    }
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Esporta stats JSON per il frontend")
    parser.add_argument("--db", required=True)
    parser.add_argument("--docs", required=True)
    return parser.parse_args()


def compute_stats(matches: List[Dict]) -> Dict:
    by_player: Dict[str, Dict] = {}
    by_team: Dict[str, Dict] = {}
    solo_vs_team: Dict[str, Dict] = {}

    for match in matches:
        for side in match["sides"]:
            win = 1 if side["is_winner"] else 0
            side_size = len(side["players"])
            default_team_name = side.get("team_name") or "-".join(side["players"])

            for player in side["players"]:
                entry = by_player.setdefault(player, {"player": player, "games": 0, "wins": 0})
                entry["games"] += 1
                entry["wins"] += win

                split = solo_vs_team.setdefault(
                    player,
                    {
                        "player": player,
                        "solo_games": 0,
                        "solo_wins": 0,
                        "team_games": 0,
                        "team_wins": 0,
                    },
                )
                if side_size == 1:
                    split["solo_games"] += 1
                    split["solo_wins"] += win
                else:
                    split["team_games"] += 1
                    split["team_wins"] += win

            team_players = sorted(side["players"])
            if len(team_players) >= 2:
                team_key = "|".join(team_players)
                label = " + ".join(team_players)
                entry = by_team.setdefault(
                    team_key,
                    {
                        "team_key": team_key,
                        "team_label": label,
                        "team_name": default_team_name,
                        "games": 0,
                        "wins": 0,
                    },
                )
                entry["games"] += 1
                entry["wins"] += win
                if not entry.get("team_name"):
                    entry["team_name"] = default_team_name

    player_rows = list(by_player.values())
    for row in player_rows:
        row["winrate"] = round(row["wins"] / row["games"], 4) if row["games"] else 0.0
    player_rows.sort(key=lambda x: (-x["winrate"], -x["games"], x["player"]))

    team_rows = list(by_team.values())
    for row in team_rows:
        row["winrate"] = round(row["wins"] / row["games"], 4) if row["games"] else 0.0
    team_rows.sort(key=lambda x: (-x["winrate"], -x["games"], x["team_label"]))

    split_rows = list(solo_vs_team.values())
    for row in split_rows:
        row["solo_winrate"] = round(row["solo_wins"] / row["solo_games"], 4) if row["solo_games"] else None
        row["team_winrate"] = round(row["team_wins"] / row["team_games"], 4) if row["team_games"] else None
        solo_value = row["solo_winrate"] if row["solo_winrate"] is not None else 0.0
        team_value = row["team_winrate"] if row["team_winrate"] is not None else 0.0
        row["delta"] = round(team_value - solo_value, 4)
    split_rows.sort(
        key=lambda x: (
            -abs(x["delta"]),
            -(x["solo_games"] + x["team_games"]),
            x["player"],
        )
    )

    players = sorted(by_player.keys())
    courses = sorted({m["course"] for m in matches if m.get("course")})

    return {
        "version": "golf-stats.v2",
        "counts": {
            "matches": len(matches),
            "players": len(players),
            "teams": len(team_rows),
        },
        "filters": {
            "players": players,
            "courses": courses,
        },
        "by_player": player_rows,
        "by_team": team_rows,
        "solo_vs_team": split_rows,
        "matches": matches,
    }


def main() -> int:
    args = parse_args()
    docs = Path(args.docs)
    data_dir = docs / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    conn = connect(args.db)
    ensure_schema(conn)
    matches = fetch_matches(conn)
    payload = compute_stats(matches)

    (data_dir / "stats.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (data_dir / "match.schema.json").write_text(json.dumps(MATCH_SCHEMA, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Creato {data_dir / 'stats.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
