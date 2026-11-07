# AP Top 25 WBB Home Game Finder

A single-file Python script that fetches the current **AP Top 25 women's
college basketball rankings** from ESPN and lists each ranked team's
**upcoming home games** within a configurable date window. Results print to
the console and can optionally be exported to CSV — either as a fresh file
or appended to a growing tracking file for daily use.

No API key, account, or paid data source is required.

---

## Table of Contents

1. [What It Does](#what-it-does)
2. [Requirements & Installation](#requirements--installation)
3. [Quick Start](#quick-start)
4. [Command-Line Options](#command-line-options)
5. [How It Works](#how-it-works)
6. [Understanding `--days`](#understanding---days)
7. [CSV Export](#csv-export)
8. [Append Mode (Daily Tracking)](#append-mode-daily-tracking)
9. [Example Runs](#example-runs)
10. [CSV Column Reference](#csv-column-reference)
11. [Caveats & Limitations](#caveats--limitations)
12. [Troubleshooting](#troubleshooting)
13. [Automating Daily Runs](#automating-daily-runs)

---

## What It Does

For every team in the current **AP Top 25** (women's D1 basketball), the
script:

1. **Fetches the AP poll** from ESPN's public rankings endpoint.
2. **Queries each team's full-season schedule** from ESPN's team schedule
   endpoint.
3. **Filters** to future games where that team is the **home team**.
4. **Applies a date horizon** (`--days N`) to control how far ahead to look.
5. **Prints a table** of qualifying home games to standard output.
6. **Optionally writes a CSV** (new file or append) with a timestamp so you
   can track changes across runs.

---

## Requirements & Installation

### Python

- Python **3.10+** (the script uses `from __future__ import annotations` and
  modern union type hints like `dict | None`; 3.10+ is recommended).

### Dependencies

Only one third-party package:

```bash
pip install requests
```

Everything else is in the standard library (`argparse`, `csv`, `datetime`,
`pathlib`, `sys`).

### Setup

1. Save the script as `wbb_ranked_next_home.py`.
2. Install `requests` (above).
3. Run it (see Quick Start).

No configuration file, environment variable, or API key is needed.

---

## Quick Start

```
# Show each ranked team's next home game
python wbb_ranked_next_home.py

# Show all ranked home games in the next two weeks
python wbb_ranked_next_home.py --days 14

# ...and write the results to a fresh CSV
python wbb_ranked_next_home.py --days 14 --csv

# ...and append to a tracking file instead (for daily runs)
python wbb_ranked_next_home.py --days 14 --csv --csv-append --csv-path tracking.csv
```

---

## Command-Line Options

| Flag ↕▾ | Type ↕▾ | Default ↕▾ | Description ↕▾ |
|---|---|---|---|
| −`--days N` | int | `1` | Look-ahead window in days. `1` = just the next home game per team; larger values widen the date window and may return multiple games per team. Must be `>= 1`. |
| `--csv` | flag | off | Write results to a CSV file. |
| `--csv-path PATH` | str | auto | Output CSV path. If omitted, a timestamped filename is generated: `wbb_home_games_YYYYMMDD_HHMMSS.csv`. Parent directories are created automatically. |
| `--csv-append` | flag | off | Append to the CSV instead of overwriting. Requires `--csv`. If the file does not exist (or is empty), a header row is written; otherwise only data rows are appended. |
| `-h`, `--help` | flag | — | Show usage and exit. |
⚙

### Validation rules

- `--days` must be `>= 1`; otherwise the script exits with an error.
- `--csv-append` without `--csv` is an error (you can't append without
enabling CSV output).

---

## How It Works

### Step 1 — Fetch AP Top 25

The script calls:

```
GET https://site.api.espn.com/apis/site/v2/sports/basketball/womens-college-basketball/rankings
```

ESPN returns multiple polls (AP, Coaches, etc.). The script picks the poll
whose name contains `"ap"`. If none is found (rare), it falls back to the
first poll and prints a warning.

For each ranked team it records:

- ESPN **team ID** (stable numeric identifier)
- **AP rank** (1–25)
- **Display name**

Only teams with `rank <= 25` are kept. Rankings are keyed by team ID so
matching against schedules is exact — no fragile name-string comparison.

### Step 2 — Query each team's schedule

For every ranked team:

```
GET https://site.api.espn.com/apis/site/v2/sports/basketball/womens-college-basketball/teams/{team_id}/schedule
```

This returns the **entire season schedule** for that team, including past
and future games.

### Step 3 — Filter to future home games

For each event:

- Parse the ISO date (skip malformed dates).
- Skip if the game has already started (`date <= now`, UTC).
- Confirm exactly two competitors and identify home/away via `homeAway`.
- Confirm the **home team's ID equals the ranked team's ID** (this is the
core "ranked team playing at home" criterion).
- Record date, opponent, and venue.

Games are sorted ascending by date.

### Step 4 — Apply the date horizon

See the next section.

### Step 5 — Output

A fixed-width console table is printed, followed by a summary count. If
`--csv` is set, the same rows are written to CSV.

---

## Understanding `--days`

`--days` is a **date horizon**, not a game count. Its behavior has one
special case:

| `--days` ↕▾ | Behavior ↕▾ |
|---|---|
| −`1` (default) | Returns **exactly the single next home game** per team — even if that game is 10 days away. Preserves the "next scheduled home game" semantics. |
| `2` or more | Returns **all home games** whose start time falls within the next `N` days from now. A team may have 0, 1, or several qualifying games. |
⚙

### Why the special case for `1`?

With a strict 24-hour window, most teams would show "no games" on any given
day, making the default output nearly empty. `--days 1` is therefore
interpreted as "just the next one," which is what most users want from a
default run. To get a true 24-hour filter, use `--days 2` (or higher) and
inspect the dates.

---

## CSV Export

Enable with `--csv`. The file is written **after** the console table.

### Default filename

If `--csv-path` is omitted, a UTC-timestamped filename is generated:

```
wbb_home_games_20261107_143201.csv
wbb_home_games_20261108_143215.csv
```

This makes successive daily runs produce separate, sortable files.

### Custom path

```
python wbb_ranked_next_home.py --csv --csv-path data/november.csv
```

Parent directories are created automatically (`data/` in the example).

### Empty-team rows

Teams with **no** qualifying home games still produce one CSV row, with
`game_date_utc`, `opponent`, and `venue` left empty. This keeps the CSV a
complete snapshot of all 25 teams. If you only want rows with real games,
filter on `game_date_utc != ""` after the fact (e.g., in Excel or pandas).

---

## Append Mode (Daily Tracking)

Use `--csv-append` (together with `--csv` and an explicit `--csv-path`) to
accumulate results into one growing file instead of creating a new one each
run:

```
python wbb_ranked_next_home.py --days 30 --csv --csv-append --csv-path tracking.csv
```

### Behavior

- **File missing or empty** → header row is written, then data rows.
- **File exists and is non-empty** → only data rows are appended (no
duplicate header).
- **`--csv-append` without `--csv`** → hard error.
- **`--csv-append` with no `--csv-path`** → appends to a new timestamped
file (technically valid but pointless; always pass `--csv-path` when
appending).

### Why this is useful

Every row carries a `run_timestamp`. Appending daily lets you:

- **Detect schedule changes** — diff the games for a given team across runs.
- **Track when games drop off** the window as they're played.
- **Build a history** of which ranked teams had home games and when.

Example analysis in pandas:

```
import pandas as pd
df = pd.read_csv("tracking.csv")
# Which games first appeared on which run?
first_seen = df.groupby(["team", "game_date_utc"])["run_timestamp"].min()
print(first_seen.sort_values())
```

---

## Example Runs

### 1. Default — next home game per team

```
python wbb_ranked_next_home.py
```

```
[+] Fetching AP Top 25... (look-ahead: 1 day(s))
[+] Loaded 25 ranked teams.

  Checking # 1 South Carolina Gamecocks... 1 home game(s)
  Checking # 2 UConn Huskies... 1 home game(s)
  Checking # 3 USC Trojans... 1 home game(s)
  ...

====================================================================================================
 AP TOP 25 WBB — HOME GAMES (next 1 day(s))
====================================================================================================
Rank  Team                         Date (UTC)           Opponent                   Venue
----------------------------------------------------------------------------------------------------
#1    South Carolina Gamecocks     2026-11-10 00:00 UTC Clemson Tigers             Colonial Life Arena
#2    UConn Huskies                2026-11-12 23:00 UTC Xavier Musketeers          XL Center
#3    USC Trojans                  2026-11-09 02:00 UTC Cal State Fullerton        Galen Center
...

 25 home game(s) across 25 ranked teams.
```

### 2. Two-week window

```
python wbb_ranked_next_home.py --days 14
```

Teams with multiple home games in the window get multiple rows; the rank
and team name are printed once and blanked on continuation rows for
readability.

### 3. CSV export

```
python wbb_ranked_next_home.py --days 7 --csv
```

```
...
[+] CSV written to: /home/user/wbb_home_games_20261107_143201.csv
```

### 4. Daily tracking with append

```
python wbb_ranked_next_home.py --days 30 --csv --csv-append --csv-path tracking.csv
```

```
...
[+] CSV appended to: /home/user/tracking.csv
```

Run this from a cron job or scheduler every morning; `tracking.csv` grows
by one run's worth of rows per day.

---

## CSV Column Reference

| Column | Description | Example |
|---|---|---|
| `run_timestamp` | UTC time the script ran (identical for all rows in one run). | `2026-11-07T14:32:01Z` |
| `rank` | AP rank of the home team (1–25). | `4` |
| `team` | Home team's ESPN display name. | `South Carolina Gamecocks` |
| `game_date_utc` | Game start time in UTC, or empty if no game in window. | `2026-11-10 00:00 UTC` |
| `opponent` | Visiting team's ESPN display name, or empty. | `Clemson Tigers` |
| `venue` | Venue full name from ESPN, or empty / `TBD`. | `Colonial Life Arena` |

---

## Caveats & Limitations

- **AP poll availability is seasonal.** The rankings endpoint returns an
empty list in the off-season; the script exits with a clear message.
- **Poll selection is name-based.** The script looks for `"ap"` in the poll
name. ESPN's naming is stable, but if it changes, the fallback (first
poll) is used with a printed warning.
- **`TBD` game times.** ESPN occasionally lists games with placeholder or
missing dates (common for some neutral-site events). Those events are
skipped rather than guessed.
- **Rankings reflect the latest poll ESPN exposes**, which may lag the
official AP release by a few hours or, rarely, until ESPN updates its
payload.
- **No odds included.** This tool is schedule/ranking only. Moneyline data
for WBB is inconsistently available from ESPN's public endpoints.
- **One schedule request per ranked team.** A full run makes ~26 HTTP
requests (1 rankings + 25 schedules). On a slow connection this can take
several seconds. No rate limiting is implemented; avoid running in tight
loops.
- **Home/away is taken from ESPN's `homeAway` field.** Neutral-site games
are typically designated with a nominal home team by ESPN; the script
treats them as home games if ESPN marks them that way. There is no
separate neutral-site filter.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `[!] No rankings returned (off-season?)` | No AP poll published (summer) | Run during the season, or wait for the preseason poll. |
| `[!] Schedule fetch failed for team NNNN` | Transient network error or ESPN hiccup | Re-run; if persistent, check connectivity / ESPN status. |
| `No home games found` for many teams | Window too narrow, or ESPN hasn't posted future games yet | Increase `--days`; verify the season schedule is published. |
| `--csv-append requires --csv` | Forgot `--csv` | Add `--csv` (and ideally `--csv-path`). |
| CSV opens with blank lines in Excel | Old Excel quirk | The script writes `newline=""`, which prevents this; if it persists, import via Data → From Text/CSV. |
| Script slow | ~26 sequential requests | Expected on slow networks; run less often or cache schedules (not built in). |

---

## Automating Daily Runs

### macOS / Linux (cron)

Run every morning at 7:00 AM local time, appending to `tracking.csv`:

```
0 7 * * * cd /path/to/script && /usr/bin/python3 wbb_ranked_next_home.py --days 30 --csv --csv-append --csv-path tracking.csv >> run.log 2>&1
```

### Windows (Task Scheduler)

- Program: `python.exe`
- Arguments: `wbb_ranked_next_home.py --days 30 --csv --csv-append --csv-path tracking.csv`
- Start in: the folder containing the script.

### Notes for automation

- Always pass an explicit `--csv-path` with `--csv-append`; otherwise each
run creates a new timestamped file.
- Redirect stdout to a log if you want to review console output later.
- The script exits non-zero only on fatal errors (bad args, missing
rankings); per-team schedule failures are logged and skipped.

---

## License

MIT — use, modify, and distribute freely.

