#!/usr/bin/env python3
"""
AP Top 25 WBB — Home Game Finder (with opponent rank + CSV export)
===================================================================

Fetches the current AP Top 25 from ESPN, then for each ranked team queries
its full season schedule and lists all scheduled HOME games within a
configurable date horizon. Includes the opponent's AP rank when the
opponent is also ranked. Optionally writes results to CSV (new file or
append to an existing file for daily tracking).

Usage:
  python wbb_ranked_next_home.py                          # next home game only
  python wbb_ranked_next_home.py --days 7                 # home games in next 7 days
  python wbb_ranked_next_home.py --days 30 --csv          # ...and write new CSV
  python wbb_ranked_next_home.py --csv --csv-path out.csv # custom filename
  python wbb_ranked_next_home.py --csv --csv-append --csv-path track.csv

Endpoints used (public, no key):
  Rankings:  /rankings
  Schedule:  /teams/{team_id}/schedule
"""

from __future__ import annotations

import argparse
import csv
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

RANKINGS_URL = (
    "https://site.api.espn.com/apis/site/v2/sports/basketball/"
    "womens-college-basketball/rankings"
)
TEAM_SCHEDULE_URL = (
    "https://site.api.espn.com/apis/site/v2/sports/basketball/"
    "womens-college-basketball/teams/{team_id}/schedule"
)
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; WBB-Screen/1.0)"}
TIMEOUT = 20

CSV_FIELDNAMES = [
    "run_timestamp",
    "rank",
    "team",
    "game_date_utc",
    "opponent",
    "opponent_rank",
    "venue",
]

# ---------------------------------------------------------------------------
# Rankings
# ---------------------------------------------------------------------------
def fetch_ap_top25() -> dict[int, dict]:
    """Return {team_id: {rank, name}} for the AP Top 25."""
    resp = requests.get(RANKINGS_URL, headers=HEADERS, timeout=TIMEOUT)
    resp.raise_for_status()
    data = resp.json()

    polls = data.get("rankings", [])
    if not polls:
        sys.exit("[!] No rankings returned (off-season?).")

    ap_poll = None
    for poll in polls:
        if "ap" in (poll.get("name") or "").lower():
            ap_poll = poll
            break
    if ap_poll is None:
        print("[!] AP poll not found; using first poll.")
        ap_poll = polls[0]

    teams: dict[int, dict] = {}
    for entry in ap_poll.get("ranks", []):
        rank = entry.get("current")
        if rank is None or rank > 25:
            continue
        team = entry.get("team", {})
        tid = team.get("id")
        if tid:
            teams[int(tid)] = {
                "rank": rank,
                "name": team.get("displayName") or team.get("name"),
            }
    return teams

# ---------------------------------------------------------------------------
# Schedule / home games
# ---------------------------------------------------------------------------
def find_home_games(team_id: int, horizon_days: int,
                    ranked: dict[int, dict]) -> list[dict]:
    """Return all future home games for a team within `horizon_days`.

    horizon_days == 1 returns just the single next home game (even if it is
    further than 24h away); larger values filter by an actual date window.

    `ranked` is the AP Top 25 mapping (team_id -> {rank, name}) and is used
    to populate the opponent's rank when the visitor is also ranked.
    """
    url = TEAM_SCHEDULE_URL.format(team_id=team_id)
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        resp.raise_for_status()
    except requests.RequestException as exc:
        print(f"  [!] Schedule fetch failed for team {team_id}: {exc}")
        return []

    events = resp.json().get("events", [])
    now = datetime.now(timezone.utc)
    cutoff = now + timedelta(days=horizon_days)

    games: list[dict] = []
    for event in events:
        raw_date = event.get("date", "")
        try:
            game_dt = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            continue

        if game_dt <= now:
            continue

        competitions = event.get("competitions", [])
        if not competitions:
            continue
        comp = competitions[0]
        competitors = comp.get("competitors", [])
        if len(competitors) != 2:
            continue

        home = next((c for c in competitors if c.get("homeAway") == "home"), None)
        away = next((c for c in competitors if c.get("homeAway") == "away"), None)
        if not home or not away:
            continue

        home_id = home.get("team", {}).get("id")
        if home_id is None or int(home_id) != team_id:
            continue

        # Look up the away team's AP rank (blank if unranked)
        away_team = away.get("team", {})
        away_id = away_team.get("id")
        opponent_rank = ""
        if away_id is not None:
            away_info = ranked.get(int(away_id))
            if away_info is not None:
                opponent_rank = away_info["rank"]

        games.append({
            "date": game_dt,
            "date_str": game_dt.strftime("%Y-%m-%d %H:%M UTC"),
            "opponent": away_team.get("displayName", "Unknown"),
            "opponent_rank": opponent_rank,
            "venue": comp.get("venue", {}).get("fullName", "TBD"),
        })

    games.sort(key=lambda g: g["date"])

    if horizon_days <= 1:
        return games[:1]
    return [g for g in games if g["date"] <= cutoff]

# ---------------------------------------------------------------------------
# CSV export (write / append)
# ---------------------------------------------------------------------------
def write_csv(rows: list[tuple[dict, dict | None]],
              path: Path, append: bool) -> None:
    """Write or append results to CSV.

    - append=False: create/overwrite the file, write a header row.
    - append=True:  append data rows. A header is written only if the file
                    does not exist yet or is empty.

    One row per game; one empty row (rank/team only) for teams with no games.
    """
    run_ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    path.parent.mkdir(parents=True, exist_ok=True)

    if append:
        file_exists = path.exists() and path.stat().st_size > 0
        mode = "a"
        write_header = not file_exists
    else:
        mode = "w"
        write_header = True

    with open(path, mode, encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDNAMES)
        if write_header:
            writer.writeheader()
        for info, game in rows:
            writer.writerow({
                "run_timestamp": run_ts,
                "rank": info["rank"],
                "team": info["name"],
                "game_date_utc": game["date_str"] if game else "",
                "opponent": game["opponent"] if game else "",
                "opponent_rank": game["opponent_rank"] if game else "",
                "venue": game["venue"] if game else "",
            })

    verb = "appended to" if append and not write_header else "written to"
    print(f"\n[+] CSV {verb}: {path.resolve()}")

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        description="List upcoming home games for AP Top 25 WBB teams."
    )
    parser.add_argument(
        "--days", type=int, default=1,
        help="Look-ahead window in days (default: 1 = next home game only).",
    )
    parser.add_argument(
        "--csv", action="store_true",
        help="Write results to CSV.",
    )
    parser.add_argument(
        "--csv-path", type=str, default=None,
        help="CSV output path (default: wbb_home_games_<timestamp>.csv).",
    )
    parser.add_argument(
        "--csv-append", action="store_true",
        help="Append to the CSV file instead of overwriting (requires --csv).",
    )
    args = parser.parse_args()

    if args.days < 1:
        sys.exit("--days must be >= 1")
    if args.csv_append and not args.csv:
        sys.exit("--csv-append requires --csv")

    print(f"[+] Fetching AP Top 25... (look-ahead: {args.days} day(s))")
    ranked = fetch_ap_top25()
    print(f"[+] Loaded {len(ranked)} ranked teams.\n")

    all_rows: list[tuple[dict, dict | None]] = []
    for team_id, info in sorted(ranked.items(), key=lambda kv: kv[1]["rank"]):
        print(f"  Checking #{info['rank']:>2} {info['name']}...", end=" ", flush=True)
        games = find_home_games(team_id, args.days, ranked)
        if games:
            print(f"{len(games)} home game(s)")
            for g in games:
                all_rows.append((info, g))
        else:
            print("no home games in window")
            all_rows.append((info, None))

    # ---- Console table ----
    print("\n" + "=" * 108)
    print(f" AP TOP 25 WBB — HOME GAMES (next {args.days} day(s))")
    print("=" * 108)
    header = (
        f"{'Rank':<5} {'Team':<28} {'Date (UTC)':<20} "
        f"{'Opponent':<26} {'Opp Rk':<7} {'Venue':<24}"
    )
    print(header)
    print("-" * len(header))

    last_rank = None
    for info, game in all_rows:
        if info["rank"] == last_rank:
            rank_col, team_col = "", ""
        else:
            rank_col = f"#{info['rank']}"
            team_col = info["name"]
            last_rank = info["rank"]

        if game:
            opp_rank = f"#{game['opponent_rank']}" if game["opponent_rank"] else ""
            print(f"{rank_col:<5} {team_col:<28} {game['date_str']:<20} "
                  f"{game['opponent']:<26} {opp_rank:<7} {game['venue']:<24}")
        else:
            print(f"{rank_col:<5} {team_col:<28} {'—':<20} {'—':<26} {'':<7} {'—':<24}")

    total_games = sum(1 for _, g in all_rows if g)
    ranked_matchups = sum(
        1 for _, g in all_rows if g and g["opponent_rank"]
    )
    print(f"\n {total_games} home game(s) across {len(ranked)} ranked teams.")
    print(f" {ranked_matchups} of them are ranked-vs-ranked matchups.")

    # ---- CSV export ----
    if args.csv:
        if args.csv_path:
            out_path = Path(args.csv_path)
        else:
            stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            out_path = Path(f"wbb_home_games_{stamp}.csv")
        write_csv(all_rows, out_path, append=args.csv_append)

if __name__ == "__main__":
    main()
