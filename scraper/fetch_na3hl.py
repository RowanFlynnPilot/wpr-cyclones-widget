#!/usr/bin/env python3
"""
NA3HL Data Scraper (Wausau Cyclones)

Fetches schedule, standings, and skater/goalie stats from the GameSheet
stats gateway (the same API that powers na3hl.com's stats pages) and writes
static JSON files to docs/data/cyclones/ for the widget to consume.

API base:  https://gateway.gamesheet.io/stats
Auth:      X-Gamesheet-Partner-ApiKey header (public key shipped in
           na3hl.com's client-side widget bundle — see CLAUDE.md for how
           it was found)

Everything the widget renders — including per-game goal scorers, period
linescores, shots, and power-play numbers — comes from the single
/unifiedschedule endpoint, so the widget never talks to the API directly.

Usage:
    python fetch_na3hl.py
    python fetch_na3hl.py --schedule-only
    python fetch_na3hl.py --standings-only
    python fetch_na3hl.py --stats-only
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import requests
except ImportError:
    print("ERROR: requests library required. Install with: pip install requests")
    sys.exit(1)

API_BASE = "https://gateway.gamesheet.io/stats"
API_KEY = "xtIvURA3zEEc4YZSaTDL"  # public — embedded in na3hl.com's widget JS

TEAM = {
    "slug": "cyclones",
    "name": "Wausau Cyclones",
    "league": "NA3HL",
    # GameSheet IDs are per-season. Bump both at season rollover — see CLAUDE.md.
    "season_id": 15275,       # 2026-27 NA3HL
    "season_label": "2026-27 NA3HL",
    "team_id": 525857,        # Wausau Cyclones within season 15275
    "club_id": 63,            # stable across seasons; use to find the new team_id
    "division": "Central Division",
}

OUTPUT_DIR = Path(__file__).parent.parent / "docs" / "data" / TEAM["slug"]

# GameSheet status string -> widget status_code contract
# 0 = Scheduled · 1 = In Progress · 2 = Final · 3 = Postponed · 4 = Cancelled
STATUS_CODES = {"scheduled": 0, "final": 2, "postponed": 3, "cancelled": 4}


def fetch_json(endpoint, params):
    """GET an endpoint on the GameSheet gateway. Fails loudly — a broken feed
    should fail the Actions run, not silently commit empty data."""
    url = f"{API_BASE}/{endpoint}"
    print(f"  Fetching {url} {params} ...")
    resp = requests.get(
        url,
        params=params,
        headers={"X-Gamesheet-Partner-ApiKey": API_KEY, "Content-Type": "application/json"},
        timeout=20,
    )
    resp.raise_for_status()
    payload = resp.json()
    if payload.get("status") != "success":
        raise RuntimeError(f"API returned non-success for {endpoint}: {payload}")
    return payload["data"]


def parse_game_date(label):
    """'Sep 4, 2026' -> ('2026-09-04', 'Fri')."""
    dt = datetime.strptime(label, "%b %d, %Y")
    return dt.strftime("%Y-%m-%d"), dt.strftime("%a")


def side_summary(side):
    """Per-team block within a game: score, linescore, scorers, shots, PP."""
    goals_by_period = side.get("goalsByPeriod") or {}
    periods = {str(k): v for k, v in goals_by_period.items() if str(k) != "final"}
    return {
        "id": side.get("id"),
        "name": side.get("title", ""),
        "abbr": side.get("abbr", ""),
        "logo": side.get("logo", ""),
        "goals": side.get("goals"),
        "result": side.get("result", ""),
        "periods": periods,
        "scorers": [
            {
                "name": f"{(g.get('firstName') or '').title()} {(g.get('lastName') or '').title()}".strip(),
                "period": g.get("period", ""),
                "clock": g.get("clockTime", ""),
            }
            for g in (side.get("goalDetails") or [])
        ],
        "shots": side.get("shots"),
        "pp_goals": side.get("ppGoals"),
        "pp_opportunities": side.get("ppOpportunities"),
        "record": side.get("overallRecord", ""),
    }


def fetch_schedule():
    """Full season schedule for the Cyclones, with box-score detail embedded
    on completed games (goal scorers, periods, shots, PP)."""
    games_raw = fetch_json(
        "unifiedschedule",
        {
            "filter[seasons]": TEAM["season_id"],
            "filter[teams]": TEAM["team_id"],
            "filter[limit]": 200,
        },
    )

    games = []
    for g in games_raw:
        home, visitor = g["home"], g["visitor"]
        is_home = home.get("id") == TEAM["team_id"]
        us, them = (home, visitor) if is_home else (visitor, home)

        iso_date, day_abbr = parse_game_date(g["date"])
        status = (g.get("status") or "").lower()
        status_code = STATUS_CODES.get(status, 1)

        entry = {
            "id": g["gameId"],
            "number": g.get("number", ""),
            "date": iso_date,
            "day": day_abbr,
            "time": (g.get("time") or "").strip(),
            "home": is_home,
            "opponent": them.get("title", ""),
            "opponent_abbr": them.get("abbr", ""),
            "opponent_logo": them.get("logo", ""),
            "location": g.get("location", ""),
            "status": g.get("status", ""),
            "status_code": status_code,
            "game_type": g.get("gameType", ""),
            "broadcast": (g.get("data") or {}).get("broadcaster", ""),
        }

        if status_code >= 1 and us.get("goals") is not None:
            entry["our_score"] = us.get("goals")
            entry["opponent_score"] = them.get("goals")
            # Overtime/shootout if either side scored in a period beyond the 3rd.
            extra = [
                p
                for side in (us, them)
                for p in (side.get("goalsByPeriod") or {})
                if str(p) not in ("1", "2", "3", "final")
            ]
            entry["overtime"] = len(extra) > 0
            entry["attendance"] = g.get("attendance")
            entry["us"] = side_summary(us)
            entry["them"] = side_summary(them)

        games.append(entry)

    games.sort(key=lambda x: (x["date"], x["time"]))
    return {
        "season": TEAM["season_label"],
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "total_games": len(games),
        "games": games,
    }


def fetch_standings():
    """Central Division standings (overall)."""
    data = fetch_json(
        "standings",
        {
            "filter[seasons]": TEAM["season_id"],
            "filter[gametype]": "overall",
            "filter[venueType]": "overall",
            "filter[divisions]": "overall",
        },
    )
    rows = data[0]["standings"]
    central = [r for r in rows if r["division"]["title"] == TEAM["division"]]
    central.sort(key=lambda r: r["rank"])

    teams = []
    for r in central:
        s = r["stats"]
        t = r["team"]
        teams.append(
            {
                "rank": r["rank"],
                "team_id": t["id"],
                "name": t["title"],
                "abbr": t.get("abbreviation", ""),
                "logo": t.get("logoUrl", ""),
                "GP": s["GP"],
                "W": s["W"],
                "L": s["L"],
                "OTL": s["OTL"],  # note: OTSOL in the feed is OTL+SOL combined, not additive
                "SOL": s["SOL"],
                "PTS": s["PTS"],
                "GF": s["GF"],
                "GA": s["GA"],
                "STK": s.get("STK", ""),
                "P10": s.get("P10", ""),
                "record": s.get("GTYPEREC", ""),   # W-L-OTL-SOL
                "home_record": s.get("HREC", ""),
                "away_record": s.get("VREC", ""),
            }
        )

    return {
        "season_name": TEAM["season_label"],
        "division": TEAM["division"],
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "teams": teams,
    }


def fetch_stats():
    """Season skater + goalie stats for Cyclones players only."""
    base = {
        "filter[seasons]": TEAM["season_id"],
        "filter[gametype]": "overall",
        "filter[teams]": TEAM["team_id"],
        "filter[limit]": 60,
    }
    skaters_raw = fetch_json("players", base)
    goalies_raw = fetch_json("goalies", base)

    def jersey(p):
        for t in p.get("teams", []):
            if t.get("id") == TEAM["team_id"]:
                return t.get("jersey", ""), (t.get("positions") or [""])[0]
        return "", ""

    skaters = []
    for p in skaters_raw:
        s = p.get("stats") or {}
        num, pos = jersey(p)
        skaters.append(
            {
                "name": f"{(p.get('firstName') or '').title()} {(p.get('lastName') or '').title()}".strip(),
                "jersey": num,
                "pos": pos[:1].upper() if pos else "",
                "GP": s.get("gp", 0),
                "G": s.get("g", 0),
                "A": s.get("a", 0),
                "PTS": s.get("pts", 0),
                "PIM": s.get("pim", 0),
                "PPG": s.get("ppg", 0),
                "GWG": s.get("gwg", 0),
                "PTSPG": s.get("ptspg", 0),
            }
        )
    skaters.sort(key=lambda x: (-x["PTS"], -x["G"]))

    goalies = []
    for p in goalies_raw:
        s = p.get("stats") or {}
        num, _ = jersey(p)
        sv = s.get("svpct")
        goalies.append(
            {
                "name": f"{(p.get('firstName') or '').title()} {(p.get('lastName') or '').title()}".strip(),
                "jersey": num,
                "GP": s.get("gp", 0),
                "W": s.get("wins", 0),
                "L": s.get("losses", 0),
                "OTL": s.get("otl", 0),
                "GA": s.get("ga", 0),
                "SA": s.get("sa", 0),
                "SVPCT": round(sv, 3) if isinstance(sv, (int, float)) else 0,
                "GAA": round(s.get("gaa", 0), 2),
                "SO": s.get("so", 0),
            }
        )
    goalies.sort(key=lambda x: (-x["GP"], x["GAA"]))

    return {
        "season_name": TEAM["season_label"],
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "skaters": skaters,
        "goalies": goalies,
    }


def write_json(filename, data):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    filepath = OUTPUT_DIR / filename
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"  Wrote {filepath} ({filepath.stat().st_size:,} bytes)")


def main():
    parser = argparse.ArgumentParser(description="Fetch NA3HL data for the Wausau Cyclones")
    parser.add_argument("--schedule-only", action="store_true")
    parser.add_argument("--standings-only", action="store_true")
    parser.add_argument("--stats-only", action="store_true")
    args = parser.parse_args()
    only_flags = [args.schedule_only, args.standings_only, args.stats_only]
    fetch_all = not any(only_flags)

    print(f"\n=== {TEAM['name']} ({TEAM['season_label']}) — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===")

    if fetch_all or args.schedule_only:
        print("\n[schedule]")
        schedule = fetch_schedule()
        write_json("schedule.json", schedule)
        finals = sum(1 for g in schedule["games"] if g["status_code"] == 2)
        print(f"  -> {schedule['total_games']} games ({finals} final)")

    if fetch_all or args.standings_only:
        print("\n[standings]")
        standings = fetch_standings()
        write_json("standings.json", standings)
        print(f"  -> {len(standings['teams'])} teams in {standings['division']}")

    if fetch_all or args.stats_only:
        print("\n[stats]")
        stats = fetch_stats()
        write_json("stats.json", stats)
        print(f"  -> {len(stats['skaters'])} skaters, {len(stats['goalies'])} goalies")

    write_json(
        "meta.json",
        {
            "last_scrape": datetime.now(timezone.utc).isoformat(),
            "season_id": TEAM["season_id"],
            "team_id": TEAM["team_id"],
            "team_name": TEAM["name"],
            "league": TEAM["league"],
            "api_base": API_BASE,
        },
    )

    print("\n✓ Done!")


if __name__ == "__main__":
    main()
