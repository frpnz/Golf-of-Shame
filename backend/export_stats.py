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


def match_year(match: Dict) -> str | None:
    played_at = str(match.get("played_at") or "").strip()
    if len(played_at) >= 4 and played_at[:4].isdigit():
        return played_at[:4]
    return None


def empty_h2h_entry() -> Dict:
    return {
        "games": 0,
        "wins": 0,
        "draws": 0,
        "losses": 0,
        "points_for": 0,
        "points_against": 0,
    }


def side_points(side: Dict, is_draw: bool) -> int:
    if not side.get("is_winner"):
        return 0
    return 1 if is_draw else 3


def add_h2h_result(matrix: Dict[str, Dict[str, Dict]], source: str, target: str, source_points: int, target_points: int) -> None:
    if source == target:
        return
    entry = matrix.setdefault(source, {}).setdefault(target, empty_h2h_entry())
    entry["games"] += 1
    entry["points_for"] += source_points
    entry["points_against"] += target_points
    if source_points > target_points:
        entry["wins"] += 1
    elif source_points < target_points:
        entry["losses"] += 1
    else:
        entry["draws"] += 1


def compute_head_to_head(matches: List[Dict], player_labels: List[str], team_rows: List[Dict]) -> Dict:
    player_label_set = set(player_labels)
    team_label_by_key = {
        row["team_key"]: row.get("team_name") or row.get("team_label") or row["team_key"]
        for row in team_rows
    }
    team_key_by_label = {}
    for key, label in team_label_by_key.items():
        # If labels collide, keep a stable component-based fallback for uniqueness.
        if label in team_key_by_label and team_key_by_label[label] != key:
            label = key.replace("|", " + ")
            team_label_by_key[key] = label
        team_key_by_label[label] = key

    players_matrix: Dict[str, Dict[str, Dict]] = {label: {} for label in player_labels}
    teams_matrix: Dict[str, Dict[str, Dict]] = {label: {} for label in team_label_by_key.values()}

    for match in matches:
        is_draw = bool(match.get("is_draw"))
        enriched_sides = []
        for side in match.get("sides", []):
            players = sorted(side.get("players") or [])
            enriched_sides.append({
                "players": players,
                "points": side_points(side, is_draw),
                "team_key": "|".join(players) if len(players) >= 2 else None,
            })

        # Head2Head - Player: consider only true individual 1v1 matches.
        # Player points earned as members of a team still count in the player standings,
        # but they are intentionally excluded from this matrix.
        is_individual_1v1 = (
            len(enriched_sides) == 2
            and all(len(side["players"]) == 1 for side in enriched_sides)
        )

        for i, source_side in enumerate(enriched_sides):
            for j, target_side in enumerate(enriched_sides):
                if i == j:
                    continue

                if is_individual_1v1:
                    source_player = source_side["players"][0]
                    target_player = target_side["players"][0]
                    if (
                        source_player in player_label_set
                        and target_player in player_label_set
                        and source_player != target_player
                    ):
                        add_h2h_result(
                            players_matrix,
                            source_player,
                            target_player,
                            source_side["points"],
                            target_side["points"],
                        )

                source_team_key = source_side.get("team_key")
                target_team_key = target_side.get("team_key")
                if not source_team_key or not target_team_key or source_team_key == target_team_key:
                    continue
                source_team = team_label_by_key.get(source_team_key)
                target_team = team_label_by_key.get(target_team_key)
                if not source_team or not target_team:
                    continue
                add_h2h_result(
                    teams_matrix,
                    source_team,
                    target_team,
                    source_side["points"],
                    target_side["points"],
                )

    return {
        "players": {
            "labels": player_labels,
            "matrix": players_matrix,
        },
        "teams": {
            "labels": list(team_label_by_key.values()),
            "matrix": teams_matrix,
        },
    }


def tie_breaker_label(row: Dict) -> str:
    direct_points = row.get("tie_direct_points")
    if direct_points is None:
        return "-"
    return f"SD {direct_points} · V {row.get('wins', 0)} · WR {round((row.get('winrate') or 0) * 100)}%"


def apply_tie_breakers(rows: List[Dict], label_key: str, matrix: Dict[str, Dict[str, Dict]]) -> None:
    groups: Dict[int, List[Dict]] = {}
    for row in rows:
        groups.setdefault(int(row.get("points") or 0), []).append(row)
        row["tie_direct_points"] = 0
        row["tie_direct_wins"] = 0
        row["tie_breaker"] = "-"

    for tied_rows in groups.values():
        if len(tied_rows) < 2:
            continue
        tied_labels = [row[label_key] for row in tied_rows]
        for row in tied_rows:
            label = row[label_key]
            direct_points = 0
            direct_wins = 0
            for opponent in tied_labels:
                if opponent == label:
                    continue
                entry = (matrix.get(label) or {}).get(opponent) or {}
                direct_points += int(entry.get("points_for") or 0)
                direct_wins += int(entry.get("wins") or 0)
            row["tie_direct_points"] = direct_points
            row["tie_direct_wins"] = direct_wins
            row["tie_breaker"] = tie_breaker_label(row)


def ranking_key(label_key: str):
    def key(row: Dict):
        return (
            -int(row.get("points") or 0),
            -int(row.get("tie_direct_points") or 0),
            -int(row.get("tie_direct_wins") or 0),
            -int(row.get("wins") or 0),
            -(row.get("winrate") or 0),
            -(row.get("points_rate") or 0),
            str(row.get(label_key) or "").lower(),
        )
    return key


def compute_view(matches: List[Dict]) -> Dict:
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

    team_rows = list(by_team.values())
    for row in team_rows:
        row["points_rate"] = round(row["points"] / row["games"], 4) if row["games"] else 0.0
        row["winrate"] = round(row["wins"] / row["games"], 4) if row["games"] else 0.0

    # Calcola gli scontri diretti prima dell'ordinamento finale: servono anche come tie breaker.
    head_to_head = compute_head_to_head(
        matches,
        sorted([row["player"] for row in player_rows]),
        sorted(team_rows, key=lambda row: row.get("team_label") or ""),
    )

    team_display_by_key = {
        row["team_key"]: row.get("team_name") or row.get("team_label") or row["team_key"]
        for row in team_rows
    }
    for row in team_rows:
        row["_h2h_label"] = team_display_by_key[row["team_key"]]

    apply_tie_breakers(player_rows, "player", head_to_head["players"]["matrix"])
    apply_tie_breakers(team_rows, "_h2h_label", head_to_head["teams"]["matrix"])

    player_rows.sort(key=ranking_key("player"))
    team_rows.sort(key=ranking_key("team_label"))

    for row in team_rows:
        row.pop("_h2h_label", None)

    head_to_head["players"]["labels"] = [row["player"] for row in player_rows]
    head_to_head["teams"]["labels"] = [row.get("team_name") or row.get("team_label") or row["team_key"] for row in team_rows]

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
        "head_to_head": head_to_head,
        "matches": matches,
    }


def compute_stats(matches: List[Dict]) -> Dict:
    years = sorted({year for match in matches if (year := match_year(match))}, reverse=True)
    views = {"all": compute_view(matches)}
    for year in years:
        views[year] = compute_view([match for match in matches if match_year(match) == year])

    payload = {
        "version": "golf-stats.v6",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scoring": {
            "win_points": 3,
            "draw_points": 1,
            "loss_points": 0,
            "winrate_rule": "wins / games; draws are not counted as wins",
        },
        "years": years,
        "views": views,
    }

    # Backward-compatible root fields: equivalent to views.all.
    payload.update(views["all"])
    return payload


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
