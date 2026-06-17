[README.md](https://github.com/user-attachments/files/29041850/README.md)
# Lineup Leak Bot — MLB lineup comparison backend

This is a starter Flask API for an iPhone Shortcuts-powered MLB Lineup Leak workflow.

## What it does

- Takes a team code and date.
- Finds that team's MLB game.
- Pulls today's confirmed lineup from MLB Stats API game feed when available.
- Pulls yesterday's lineup.
- Compares continuity and returns a Lineup Leak score.
- Returns `shortcut_text`, which is formatted for iPhone Shortcuts notifications.

## Run locally

```bash
pip install -r requirements.txt
python app.py
```

Open:

```text
http://127.0.0.1:5000/lineup-leak?team=CHC&date=2026-06-13
```

## Deploy on Render/Railway/Replit

Start command:

```bash
gunicorn app:app
```

## iPhone Shortcut setup

1. Open Shortcuts.
2. Create new shortcut: `Run Lineup Leak`.
3. Add action: `Text` → enter your team code, like `CHC`.
4. Add action: `Get Contents of URL`.
5. URL:

```text
https://YOUR-APP-URL.onrender.com/lineup-leak?team=CHC
```

6. Add action: `Get Dictionary Value` → key `shortcut_text`.
7. Add action: `Show Result` or `Show Notification`.

## Automation idea

Create a Personal Automation that runs every day around 2–4 hours before the team's first pitch, or manually run it when lineup tweets/pages start dropping.

## Team codes

ARI, ATL, BAL, BOS, CHC, CWS, CIN, CLE, COL, DET, HOU, KC, LAA, LAD, MIA, MIL, MIN, NYM, NYY, ATH, PHI, PIT, SD, SEA, SF, STL, TB, TEX, TOR, WSH

## Notes

This starter does not place bets and does not guarantee picks. It only creates a lineup continuity signal. You should add your own filters for pitcher handedness, opposing bullpen quality, player props, odds movement, injuries, and weather.
