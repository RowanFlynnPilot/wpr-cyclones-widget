# WPR Cyclones Widget

## Project Overview
Embeddable widget for **Wausau Pilot & Review** covering the **Wausau Cyclones** (junior hockey, NA3HL Central Division). Structurally a sibling of `wpr-woodchucks-widget` — same tab layout, embed contract, mini variants, and WPR sponsor band — adapted for hockey and a different league data platform. One self-contained HTML file; the team is picked from `?team=cyclones` in the URL and defaults to `cyclones`.

Deployed to GitHub Pages and embedded in WPR's WordPress site via iframe.

## Architecture
```
scraper/fetch_na3hl.py
  ↓ (GitHub Actions cron, every ~30 min during game hours Sep–Mar)
docs/data/cyclones/{schedule,standings,stats,meta}.json
docs/data/cyclones/events.json (hand-edited from the team's promo announcements)
  ↓
docs/index.html (single file, reads ?team= URL param)
  ↓ (GitHub Pages serves from /docs)
WordPress iframe with postMessage auto-resize listener
```

**Key difference from the Woodchucks widget:** the frontend is fully static — it never calls the league API. The `/unifiedschedule` endpoint returns complete box-score detail (goal scorers, period linescores, shots, power play, attendance) with every game, so the scraper embeds it all in `schedule.json` and the widget's recap lines, Results cards, and game-detail modal render synchronously with no per-game fetches. There are no fallback data paths: if a JSON file is missing, the tab shows an error state.

## Data Source

| What | Value |
|---|---|
| API base | `https://gateway.gamesheet.io/stats` |
| Auth header | `X-Gamesheet-Partner-ApiKey: xtIvURA3zEEc4YZSaTDL` |
| Season (2026-27 NA3HL) | `season_id=15275` |
| Wausau Cyclones team | `team_id=525857` (per-season), `club_id=63` (stable) |
| Division | `Central Division` (id 82056 in 2026-27) |

### How the API was found
na3hl.com renders its stats pages with HockeyTech's WTD React widget
(`https://images-us-east.htptv.net/wtd/main.react.js`). The bundle creates an
axios instance with the gateway base URL and the partner API key hardcoded —
grep the bundle for `gateway.gamesheet.io` to re-verify if the key ever
rotates. The page-level config (`window.customconfiguration` on any na3hl.com
stats page) carries `league_id: 5` (site-internal) and `gs_league_id: 1148419`
(the GameSheet league id used by the API).

**Note:** `gamesheetstats.com` (the public GameSheet site) sits behind a
Cloudflare challenge that blocks datacenter IPs — GitHub Actions runners
included. `gateway.gamesheet.io` has no such challenge; use the gateway.

### Endpoints used (all GET, all take `filter[...]` query params)
- `/seasons?filter[leagues]=1148419` — season list; how to find next season's id
- `/teams?filter[seasons]={sid}&filter[gametype]=overall` — team ids, divisions, logos
- `/unifiedschedule?filter[seasons]={sid}&filter[teams]={tid}&filter[limit]=200` — schedule **with embedded box scores** on final games
- `/standings?filter[seasons]={sid}&filter[gametype]=overall&filter[venueType]=overall&filter[divisions]=overall` — full-league standings; scraper filters to the Central Division
- `/players` / `/goalies` with `filter[seasons]`, `filter[teams]`, `filter[gametype]=overall` — season stat lines

### Feed quirks worth remembering
- Game `status` strings seen so far: `scheduled`, `final`. Scraper maps
  postponed→3, cancelled→4, anything else unknown→1 (treated as live).
- `goalsByPeriod` keys are `"1" "2" "3"` plus `"ot_1"` (and presumably `"so"`)
  and a `"final"` total. The widget derives OT/SO tags from the extra keys.
- Standings `OTSOL` is **OTL+SOL combined**, not a separate bucket — don't add
  it to OTL (that double-counts; a team's GP must equal W+L+OTL+SOL).
- `GTYPEREC` is the league-format record string `W-L-OTL-SOL`; `HREC`/`VREC`
  are the home/away splits. The record banner uses these directly.
- Logos are served from `imagedelivery.net` (Cloudflare Images) and hotlink
  fine. The Cyclones logo is also self-hosted at `docs/cyclones-logo.png`.
- **Cloudflare Images URLs need a variant segment** or they 400:
  `/unifiedschedule` logos come with `/256` appended, but `/standings`
  `logoUrl` comes bare — the scraper's `normalize_logo()` appends `/256`.
- Standings `rank` is unreliable before games are played: teams tie at 1 and
  late-added teams show 0. The scraper renumbers alphabetically 1..N while
  every team has GP=0, then trusts the feed rank in-season.

## Widget JSON contract (written by the scraper)
- `schedule.json` — `games[]` with `id, date (ISO), day, time, home, opponent,
  opponent_abbr, opponent_logo, location, status, status_code, broadcast`;
  final games add `our_score, opponent_score, overtime, attendance` and full
  `us` / `them` blocks (`periods`, `scorers[{name,period,clock}]`, `shots`,
  `pp_goals`, `pp_opportunities`, `record`).
- `standings.json` — Central Division only: `teams[]` with `rank, name, abbr,
  logo, GP, W, L, OTL, SOL, PTS, GF, GA, STK, P10, record, home_record,
  away_record`.
- `stats.json` — `skaters[]` (GP G A PTS PIM PPG GWG) and `goalies[]`
  (GP W L OTL GA SA SVPCT GAA SO), Cyclones players only.
- `events.json` — editorial, same shape as the Woodchucks widget.

## Brand Palettes

### WPR (sponsor band)
- Teal: `#4aaba7` / `#3a8e8b` · Cream: `#faf7f2` · Ink: `#1a1a1a`
- Fonts: Source Sans 3 (body), Bebas Neue (display), JetBrains Mono (data/labels)

### Cyclones (team theme)
- Black: `#101010` / `#2a2a2a`
- Gold: `#f5b120` / `#ffd35c` (sampled from the official logo)
- Logo: gold cyclone swirl on black (`docs/cyclones-logo.png`, 256×256, from GameSheet's CDN)
- Gold-contrast rule: anything with a gold background uses **black text**
  (`.season-badge`, `.potg-badge`, CTAs). The one CSS deviation from the
  Woodchucks file is `.season-badge { color: var(--chucks-navy) }` and the
  `.ticket-btn:hover` text color.

CSS custom property names are inherited unchanged from the Woodchucks widget
(`--chucks-navy`, `--chucks-cyan`, …) so the two stylesheets stay diffable —
only the values differ. `applyBranding()` sets them at runtime.

## Key Files
```
docs/
  index.html              # the widget (single file, all CSS+JS inline)
  cyclones-logo.png       # 256x256, self-hosted
  wpr-logo.png            # WPR mark
  data/cyclones/
    schedule.json         # auto-updated by scraper (includes box scores)
    standings.json        # auto-updated by scraper
    stats.json            # auto-updated by scraper
    meta.json             # auto-updated by scraper
    events.json           # editorial — hand-edited
  snapshots/
    cyclones-today.png    # daily render of ?mini=tickets for email embeds
scraper/
  fetch_na3hl.py          # TEAM dict at top holds season_id/team_id
scripts/
  snapshot_cards.py       # renders the newsletter card PNG
.github/workflows/
  scrape.yml              # cron scraper (game-hour cadence Sep–Mar)
  snapshot.yml            # daily 6 AM CT PNG render
```

## WordPress Embed
Same message contract as the Woodchucks widget (`{ type: 'wpr-widget-resize',
team, height }`), so if a page already has the shared listener, only the
iframe is needed. See README for the copy-paste blocks.

The full-coverage links inside the widget (mini CTA, newsletter card) point to
`https://wausaupilotandreview.com/cyclones/` — **that WordPress landing page
needs to be created** (same pattern as `/woodchucks-ignite/`), hosting the
full-widget iframe.

## Season Timeline (2026-27)
- **Sep 4**: Season opener @ Peoria
- **Sep 25**: Home opener vs Fox Cities Forge (7:10 PM, Marathon Park)
- **Mar 14**: Regular season ends (6:10 PM Sunday home finale)
- 47 announced games; 44 in the feed as of July 2026 — the cron picks up the
  rest as the league enters them
- Fraser Cup Playoffs follow in mid-March (separate GameSheet season id — the
  league created `2026 NA3HL Fraser Cup Playoffs` as its own season last year)

## Annual Rollover Checklist (each August)
1. `GET /seasons?filter[leagues]=1148419` → find the new `XXXX-XX NA3HL` season id
2. `GET /teams?filter[seasons]={new_id}` → find the Cyclones entry via `club_id=63`, note the new `team_id`
3. Update `season_id`, `team_id`, `season_label` in `scraper/fetch_na3hl.py`;
   roll `prior_season_id` / `prior_team_id` / `prior_season_label` forward too
   if the preseason stats preview (last season's numbers + disclaimer in the
   Stats tab) is wanted again — it retires itself once the new season has
   stat lines, or set `prior_season_id` to `None` to disable it
4. Update `seasonLabel` and `seasonMonths` in the `TEAMS` block of `docs/index.html`
5. Re-curate `docs/data/cyclones/events.json` when the promo schedule drops (mid-September)

## Development
```bash
# Install scraper deps (one-time)
pip install -r scraper/requirements.txt

# Run scraper
python scraper/fetch_na3hl.py
python scraper/fetch_na3hl.py --schedule-only   # or --standings-only / --stats-only

# Preview locally
python -m http.server 8765 --directory docs
# http://localhost:8765/?team=cyclones
# http://localhost:8765/?team=cyclones&mini=true
# http://localhost:8765/?team=cyclones&mini=tickets
```

## Common Edits
- **Add an event**: edit `docs/data/cyclones/events.json`, push.
- **Brand tweaks**: change values in the `brand:` object in `docs/index.html`.
- **Second hockey team**: add an entry to `TEAMS` in `docs/index.html` and a
  matching config in the scraper (same pattern the Woodchucks repo used for
  the Ignite).
- **Playoffs**: playoff games live under a separate GameSheet season id — when
  the Cyclones clinch, either bump the scraper to fetch both seasons or wait
  for the league to publish and handle it as a one-off.
