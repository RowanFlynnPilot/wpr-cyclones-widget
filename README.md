# WPR Cyclones Widget

Embeddable **Wausau Cyclones** (NA3HL) widget for [Wausau Pilot & Review](https://wausaupilotandreview.com) — schedule, standings, results with box scores, player stats, and promotional events, updated automatically from the league's GameSheet feed.

A sibling of [`wpr-woodchucks-widget`](https://github.com/RowanFlynnPilot/wpr-woodchucks-widget): same embed contract, same WPR sponsor band, adapted for hockey.

**Live:** `https://rowanflynnpilot.github.io/wpr-cyclones-widget/?team=cyclones`

## Features

- **Schedule** — month-by-month (September through March, crossing the calendar year), home/away filter pills, ticket links on home games, one-line auto-generated recaps on completed games
- **Standings** — NA3HL Central Division with the Cyclones row highlighted, plus a record banner (record, points + division rank, home/away splits, streak)
- **Results** — newest-first cards with period linescores (1 · 2 · 3 · OT/SO · T) and Cyclones goal scorers; click any card for the full game detail (scoring summary with clock times, shots, power play, attendance)
- **Stats** — sortable skater and goalie tables for the season
- **Events** — hand-curated promotional schedule
- **Mini variants** — `?mini=true` (record + last/next game, for in-article embeds) and `?mini=tickets` (newsletter-style card with a Buy Tickets button)
- **Email snapshot** — a GitHub Action renders the tickets card to a PNG daily for newsletter embedding (iframes don't survive email clients)

The widget is fully static: the scraper embeds complete box-score detail in `schedule.json`, so the page never calls the league API.

## Architecture

```
GameSheet stats gateway (powers na3hl.com)
        │  scraper/fetch_na3hl.py — GitHub Actions cron
        ▼
docs/data/cyclones/*.json  (committed to the repo)
        │
        ▼
docs/index.html  ——  GitHub Pages  ——  WordPress iframe (auto-resizing)
```

## Setup

1. Push to GitHub, then **Settings → Pages → Deploy from branch → `main` / `docs`**
2. The two workflows (data scrape + daily snapshot) run on their own; both are manually triggerable from the Actions tab
3. Hand-edit `docs/data/cyclones/events.json` when the team announces promotions

## WordPress embed

**Full widget** (on the team landing page):

```html
<iframe
  src="https://rowanflynnpilot.github.io/wpr-cyclones-widget/?team=cyclones"
  style="width:100%;max-width:760px;border:none;display:block;margin:0 auto;"
  height="900"
  title="Wausau Cyclones schedule, standings, results and stats"
  loading="lazy"
  data-team="cyclones"></iframe>
```

**Mini widget** (inside articles):

```html
<iframe
  src="https://rowanflynnpilot.github.io/wpr-cyclones-widget/?team=cyclones&mini=true"
  style="width:100%;max-width:480px;border:none;display:block;"
  height="320"
  title="Wausau Cyclones — latest result and next game"
  loading="lazy"
  data-team="cyclones"></iframe>
```

**Auto-resize listener** (once per page, in a Custom HTML block or the theme; identical to the Woodchucks widget's listener, so if a page already has it, skip this):

```html
<script>
window.addEventListener('message', function (e) {
  if (!e.data || e.data.type !== 'wpr-widget-resize') return;
  document
    .querySelectorAll('iframe[data-team="' + e.data.team + '"]')
    .forEach(function (f) { f.height = e.data.height; });
});
</script>
```

**Newsletter (email) embed** — link the daily PNG, since email clients strip iframes:

```html
<a href="https://wausaupilotandreview.com/cyclones/">
  <img src="https://rowanflynnpilot.github.io/wpr-cyclones-widget/snapshots/cyclones-today.png"
       alt="Wausau Cyclones — latest score and next game"
       width="380" style="max-width:100%;height:auto;border:0;">
</a>
```

## Local development

```bash
pip install -r scraper/requirements.txt
python scraper/fetch_na3hl.py            # refresh data
python -m http.server 8765 --directory docs
# → http://localhost:8765/?team=cyclones
```

## Data source

Schedule, standings, and stats come from the GameSheet stats gateway — the same API that powers na3hl.com's stats pages. Endpoint and ID details, feed quirks, and the annual season-rollover checklist live in [CLAUDE.md](CLAUDE.md).

Not affiliated with the Wausau Cyclones or the NA3HL. Data is presented as-is from league sources.
