#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

from common import connect, ensure_schema, fetch_matches

MIN_GAMES_FOR_RATE_RANKING = 7

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
        "tag": {"type": ["string", "null"], "description": "Compatibilita: singolo tag/competizione. Internamente viene normalizzato in tags."},
        "tags": {
            "type": ["array", "string", "null"],
            "description": "Tag o competizioni associati alla partita. Se stringa, puoi separare piu tag con virgole.",
            "items": {"type": "string"}
        },
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


def format_points_rate(value: float | None) -> str:
    if value is None:
        return "-"
    text = f"{float(value):.2f}"
    return text.rstrip("0").rstrip(".") if "." in text else text


def points_tie_breaker_label(row: Dict, use_direct: bool) -> str:
    parts = []
    if use_direct:
        parts.append(f"SD {row.get('tie_direct_points', 0)}")
    parts.append(f"V {row.get('wins', 0)}")
    parts.append(f"Media {format_points_rate(row.get('points_rate') or 0)}")
    return " · ".join(parts)


def rate_tie_breaker_label(row: Dict) -> str:
    return f"G {row.get('games', 0)} · Pt {row.get('points', 0)} · V {row.get('wins', 0)}"


def apply_tie_breakers(rows: List[Dict], label_key: str, matrix: Dict[str, Dict[str, Dict]] | None = None, use_direct: bool = False) -> None:
    points_groups: Dict[int, List[Dict]] = {}
    rate_groups: Dict[float, List[Dict]] = {}
    for row in rows:
        points_groups.setdefault(int(row.get("points") or 0), []).append(row)
        rate_groups.setdefault(float(row.get("points_rate") or 0), []).append(row)
        row["tie_direct_points"] = 0
        row["tie_direct_wins"] = 0
        row["tie_breaker"] = "-"
        row["tie_breaker_points"] = "-"
        row["tie_breaker_rate"] = "-"

    matrix = matrix or {}
    for tied_rows in points_groups.values():
        if len(tied_rows) < 2:
            continue
        tied_labels = [row[label_key] for row in tied_rows]
        for row in tied_rows:
            if use_direct:
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
            row["tie_breaker_points"] = points_tie_breaker_label(row, use_direct=use_direct)
            row["tie_breaker"] = row["tie_breaker_points"]

    for tied_rows in rate_groups.values():
        if len(tied_rows) < 2:
            continue
        for row in tied_rows:
            row["tie_breaker_rate"] = rate_tie_breaker_label(row)


def ranking_key(label_key: str, use_direct: bool = False):
    def key(row: Dict):
        direct_values = (
            -int(row.get("tie_direct_points") or 0),
            -int(row.get("tie_direct_wins") or 0),
        ) if use_direct else ()
        return (
            -int(row.get("points") or 0),
            *direct_values,
            -int(row.get("wins") or 0),
            -(row.get("points_rate") or 0),
            str(row.get(label_key) or "").lower(),
        )
    return key


def rate_ranking_key(label_key: str):
    def key(row: Dict):
        return (
            -(row.get("points_rate") or 0),
            -int(row.get("games") or 0),
            -int(row.get("points") or 0),
            -int(row.get("wins") or 0),
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

    team_rows = list(by_team.values())
    for row in team_rows:
        row["points_rate"] = round(row["points"] / row["games"], 4) if row["games"] else 0.0

    # Calcola gli scontri diretti: per il tie breaker sono usati solo nella classifica squadre.
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

    apply_tie_breakers(player_rows, "player", use_direct=False)
    apply_tie_breakers(team_rows, "_h2h_label", head_to_head["teams"]["matrix"], use_direct=True)

    player_rows_points = sorted(player_rows, key=ranking_key("player", use_direct=False))
    player_rows_rate = sorted(player_rows, key=rate_ranking_key("player"))
    team_rows_points = sorted(team_rows, key=ranking_key("team_label", use_direct=True))
    team_rows_rate = sorted(team_rows, key=rate_ranking_key("team_label"))

    # Backward-compatible default order: absolute points.
    player_rows = player_rows_points
    team_rows = team_rows_points

    for row in team_rows:
        row.pop("_h2h_label", None)

    head_to_head["players"]["labels"] = [row["player"] for row in player_rows]
    head_to_head["teams"]["labels"] = [row.get("team_name") or row.get("team_label") or row["team_key"] for row in team_rows]

    split_rows = list(solo_vs_team.values())
    for row in split_rows:
        row["solo_points_rate"] = round(row["solo_points"] / row["solo_games"], 4) if row["solo_games"] else None
        row["team_points_rate"] = round(row["team_points"] / row["team_games"], 4) if row["team_games"] else None
        solo_value = row["solo_points_rate"] if row["solo_points_rate"] is not None else 0.0
        team_value = row["team_points_rate"] if row["team_points_rate"] is not None else 0.0
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
        "rankings": {
            "players": {
                "points": [row["player"] for row in player_rows_points],
                "points_rate": [row["player"] for row in player_rows_rate],
            },
            "teams": {
                "points": [row.get("team_name") or row.get("team_label") or row["team_key"] for row in team_rows_points],
                "points_rate": [row.get("team_name") or row.get("team_label") or row["team_key"] for row in team_rows_rate],
            },
        },
        "by_player_points_rate": player_rows_rate,
        "by_team_points_rate": team_rows_rate,
        "solo_vs_team": split_rows,
        "head_to_head": head_to_head,
        "matches": matches,
    }



def champion_from(rows: List[Dict], kind: str) -> Dict | None:
    if not rows:
        return None
    first = rows[0]
    return {
        "kind": kind,
        "name": first.get("team_name") or first.get("team_label") or "-" if kind == "team" else first.get("player") or "-",
        "points": int(first.get("points") or 0),
        "games": int(first.get("games") or 0),
        "wins": int(first.get("wins") or 0),
        "draws": int(first.get("draws") or 0),
        "losses": int(first.get("losses") or 0),
        "points_rate": first.get("points_rate") or 0,
    }


def eligible_player_rate_rows(view: Dict) -> List[Dict]:
    return [
        row for row in (view.get("by_player_points_rate") or [])
        if int(row.get("games") or 0) >= MIN_GAMES_FOR_RATE_RANKING
    ]


def view_summary(view: Dict, *, key: str, label: str, group: str) -> Dict:
    player_rate_champion = champion_from(eligible_player_rate_rows(view), "player")
    team_rate_champion = champion_from(view.get("by_team_points_rate") or [], "team")
    return {
        "key": key,
        "label": label,
        "group": group,
        "matches": int((view.get("counts") or {}).get("matches") or 0),
        "player_champion": player_rate_champion,
        "team_champion": team_rate_champion,
        "player_points_rate_champion": player_rate_champion,
        "team_points_rate_champion": team_rate_champion,
    }


def compute_stats(matches: List[Dict]) -> Dict:
    years = sorted({year for match in matches if (year := match_year(match))}, reverse=True)
    tags = sorted({tag for match in matches for tag in (match.get("tags") or [])}, key=lambda x: x.casefold())

    views: Dict[str, Dict] = {"all": compute_view(matches)}
    view_options = [
        {"value": "all", "label": "Tutte le partite", "group": "Generale"},
    ]

    untagged_matches = [match for match in matches if not (match.get("tags") or [])]
    views["untagged"] = compute_view(untagged_matches)
    view_options.append({"value": "untagged", "label": "Senza tag", "group": "Generale"})

    for year in years:
        key = f"year:{year}"
        views[key] = compute_view([match for match in matches if match_year(match) == year])
        view_options.append({"value": key, "label": year, "group": "Stagioni"})

    for tag in tags:
        key = f"tag:{tag}"
        views[key] = compute_view([match for match in matches if tag in (match.get("tags") or [])])
        view_options.append({"value": key, "label": tag, "group": "Competizioni / tag"})

    for option in view_options:
        view = views.get(option["value"], {})
        view["meta"] = {
            "key": option["value"],
            "label": option["label"],
            "group": option["group"],
        }
        view["hall_of_fame"] = view_summary(
            view,
            key=option["value"],
            label=option["label"],
            group=option["group"],
        )

    payload = {
        "version": "golf-stats.v9",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scoring": {
            "win_points": 3,
            "draw_points": 1,
            "loss_points": 0,
            "points_rate_rule": "points / games; in Italian UI this is shown as media punti",
            "player_points_rate_min_games": MIN_GAMES_FOR_RATE_RANKING,
            "ranking_modes": {
                "points": "points, then wins/direct tie breaker where applicable, then media punti, then name",
                "points_rate": "media punti, then games, then points, then wins, then name"
            },
        },
        "years": years,
        "tags": tags,
        "view_options": view_options,
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
