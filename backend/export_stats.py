#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
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
            "description": "Almeno un side deve avere is_winner=true. Se un solo side ha is_winner=true, riceve 3 punti. Se piu side hanno is_winner=true, la partita e un pareggio e ogni side marcato riceve 1 punto.",
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
        is_draw = bool(match.get("is_draw"))
        for side in match["sides"]:
            is_point_side = bool(side["is_winner"])
            is_win = is_point_side and not is_draw
            is_draw_result = is_point_side and is_draw
            points = 3 if is_win else (1 if is_draw_result else 0)
            side_size = len(side["players"])
            default_team_name = side.get("team_name") or "-".join(side["players"])

            for player in side["players"]:
                entry = by_player.setdefault(
                    player,
                    {
                        "player": player,
                        "games": 0,
                        "wins": 0,
                        "draws": 0,
                        "losses": 0,
                        "points": 0,
                    },
                )
                entry["games"] += 1
                entry["wins"] += 1 if is_win else 0
                entry["draws"] += 1 if is_draw_result else 0
                entry["losses"] += 1 if not is_point_side else 0
                entry["points"] += points

                split = solo_vs_team.setdefault(
                    player,
                    {
                        "player": player,
                        "solo_games": 0,
                        "solo_wins": 0,
                        "solo_draws": 0,
                        "solo_losses": 0,
                        "solo_points": 0,
                        "team_games": 0,
                        "team_wins": 0,
                        "team_draws": 0,
                        "team_losses": 0,
                        "team_points": 0,
                    },
                )
                prefix = "solo" if side_size == 1 else "team"
                split[f"{prefix}_games"] += 1
                split[f"{prefix}_wins"] += 1 if is_win else 0
                split[f"{prefix}_draws"] += 1 if is_draw_result else 0
                split[f"{prefix}_losses"] += 1 if not is_point_side else 0
                split[f"{prefix}_points"] += points

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
                        "components": team_players,
                        "games": 0,
                        "wins": 0,
                        "draws": 0,
                        "losses": 0,
                        "points": 0,
                    },
                )
                entry["games"] += 1
                entry["wins"] += 1 if is_win else 0
                entry["draws"] += 1 if is_draw_result else 0
                entry["losses"] += 1 if not is_point_side else 0
                entry["points"] += points
                if not entry.get("team_name"):
                    entry["team_name"] = default_team_name

    player_rows = list(by_player.values())
    for row in player_rows:
        row["points_rate"] = round(row["points"] / row["games"], 4) if row["games"] else 0.0
        row["winrate"] = round(row["wins"] / row["games"], 4) if row["games"] else 0.0
    player_rows.sort(key=lambda x: (-x["points"], -x["winrate"], -x["games"], x["player"]))

    team_rows = list(by_team.values())
    for row in team_rows:
        row["points_rate"] = round(row["points"] / row["games"], 4) if row["games"] else 0.0
        row["winrate"] = round(row["wins"] / row["games"], 4) if row["games"] else 0.0
    team_rows.sort(key=lambda x: (-x["points"], -x["winrate"], -x["games"], x["team_label"]))

    split_rows = list(solo_vs_team.values())
    for row in split_rows:
        row["solo_points_rate"] = round(row["solo_points"] / row["solo_games"], 4) if row["solo_games"] else None
        row["team_points_rate"] = round(row["team_points"] / row["team_games"], 4) if row["team_games"] else None
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
        "version": "golf-stats.v4",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scoring": {
            "win_points": 3,
            "draw_points": 1,
            "loss_points": 0,
            "winrate_rule": "wins / games; draws are not counted as wins",
        },
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
