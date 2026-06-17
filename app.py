import os
import requests
from datetime import datetime, timedelta
from flask import Flask, request, jsonify

app = Flask(__name__)

MLB_BASE = "https://statsapi.mlb.com/api/v1"

TEAM_IDS = {
    "ARI": 109, "ATL": 144, "BAL": 110, "BOS": 111, "CHC": 112, "CWS": 145,
    "CIN": 113, "CLE": 114, "COL": 115, "DET": 116, "HOU": 117, "KC": 118,
    "LAA": 108, "LAD": 119, "MIA": 146, "MIL": 158, "MIN": 142, "NYM": 121,
    "NYY": 147, "ATH": 133, "PHI": 143, "PIT": 134, "SD": 135, "SEA": 136,
    "SF": 137, "STL": 138, "TB": 139, "TEX": 140, "TOR": 141, "WSH": 120
}


def get_json(url, params=None):
    r = requests.get(url, params=params, timeout=15)
    r.raise_for_status()
    return r.json()


def get_schedule(date_str, team_id=None):
    params = {"sportId": 1, "date": date_str, "hydrate": "probablePitcher"}
    if team_id:
        params["teamId"] = team_id
    return get_json(f"{MLB_BASE}/schedule", params)


def find_team_game(date_str, team_id):
    schedule = get_schedule(date_str, team_id)
    dates = schedule.get("dates", [])
    for d in dates:
        for game in d.get("games", []):
            away = game["teams"]["away"]["team"]["id"]
            home = game["teams"]["home"]["team"]["id"]
            if team_id in (away, home):
                side = "away" if away == team_id else "home"
                opp_side = "home" if side == "away" else "away"
                return {
                    "gamePk": game["gamePk"],
                    "side": side,
                    "opponent": game["teams"][opp_side]["team"].get("name"),
                    "status": game.get("status", {}).get("detailedState"),
                    "gameDate": game.get("gameDate")
                }
    return None


def extract_lineup(game_pk, side):
    feed = get_json(f"{MLB_BASE}.1/game/{game_pk}/feed/live") if False else get_json(f"{MLB_BASE}/game/{game_pk}/feed/live")
    box_team = feed.get("liveData", {}).get("boxscore", {}).get("teams", {}).get(side, {})
    team_data = feed.get("gameData", {}).get("players", {})
    batter_ids = box_team.get("batters", []) or []

    lineup = []
    for idx, pid in enumerate(batter_ids[:9], start=1):
        pkey = f"ID{pid}"
        pdata = team_data.get(pkey, {})
        lineup.append({
            "order": idx,
            "id": pid,
            "name": pdata.get("fullName", f"Player {pid}"),
            "position": pdata.get("primaryPosition", {}).get("abbreviation", "")
        })
    return lineup


def previous_date(date_str):
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    return (dt - timedelta(days=1)).strftime("%Y-%m-%d")


def score_lineup(today, yesterday):
    if not today:
        return {
            "status": "WAITING",
            "score": None,
            "label": "LINEUP NOT POSTED",
            "notes": ["Today's confirmed lineup was not available yet."],
            "angles": []
        }

    today_ids = [p["id"] for p in today]
    y_ids = [p["id"] for p in yesterday] if yesterday else []

    same_top_5 = 0
    same_top_9 = 0
    if y_ids:
        same_top_5 = len(set(today_ids[:5]).intersection(y_ids[:5]))
        same_top_9 = len(set(today_ids[:9]).intersection(y_ids[:9]))

    score = 5.0
    notes = []

    if not yesterday:
        notes.append("No yesterday lineup found; score uses today's lineup only.")
        score += 0.5
    else:
        if same_top_5 >= 4:
            score += 2.0
            notes.append(f"Top 5 is mostly intact: {same_top_5}/5 same as yesterday.")
        elif same_top_5 >= 3:
            score += 1.0
            notes.append(f"Top 5 has moderate continuity: {same_top_5}/5 same as yesterday.")
        else:
            score -= 1.5
            notes.append(f"Top 5 changed heavily: only {same_top_5}/5 same as yesterday.")

        if same_top_9 >= 7:
            score += 1.0
            notes.append(f"Full lineup continuity is strong: {same_top_9}/9 same.")
        elif same_top_9 <= 4:
            score -= 1.0
            notes.append(f"Full lineup has major turnover: {same_top_9}/9 same.")

    # Simple structural flags
    if len(today) == 9:
        score += 0.5
        notes.append("Confirmed 9-man batting order found.")
    else:
        score -= 1.0
        notes.append("Lineup appears incomplete or not fully confirmed.")

    score = max(0, min(10, round(score, 1)))
    if score >= 7.5:
        label = "GREEN LIGHT"
    elif score >= 5.5:
        label = "SOFT PLAY / CHECK MATCHUP"
    else:
        label = "AVOID / WAIT"

    angles = []
    if score >= 7.5:
        angles = ["Top-order hitter props", "Team total lean", "Stack top 1-5 before bottom-order props"]
    elif score >= 5.5:
        angles = ["Only strongest hitters", "Avoid bottom order", "Check pitcher handedness and bullpen"]
    else:
        angles = ["Avoid forcing picks", "Wait for better lineup continuity"]

    return {"status": "READY", "score": score, "label": label, "notes": notes, "angles": angles}


@app.route("/health")
def health():
    return {"ok": True}


@app.route("/lineup-leak")
def lineup_leak():
    team = request.args.get("team", "CHC").upper().strip()
    date_str = request.args.get("date", datetime.now().strftime("%Y-%m-%d"))
    team_id = TEAM_IDS.get(team)
    if not team_id:
        return jsonify({"error": f"Unknown team code: {team}", "valid_codes": sorted(TEAM_IDS.keys())}), 400

    today_game = find_team_game(date_str, team_id)
    if not today_game:
        return jsonify({"team": team, "date": date_str, "status": "NO_GAME", "message": "No game found for this team/date."})

    today_lineup = extract_lineup(today_game["gamePk"], today_game["side"])

    y_date = previous_date(date_str)
    y_game = find_team_game(y_date, team_id)
    yesterday_lineup = []
    if y_game:
        yesterday_lineup = extract_lineup(y_game["gamePk"], y_game["side"])

    result = score_lineup(today_lineup, yesterday_lineup)

    response = {
        "team": team,
        "date": date_str,
        "game": today_game,
        "yesterday_date": y_date,
        "lineup_leak": result,
        "today_lineup": today_lineup,
        "yesterday_lineup": yesterday_lineup,
        "shortcut_text": build_shortcut_text(team, date_str, today_game, result, today_lineup, yesterday_lineup)
    }
    return jsonify(response)


def build_shortcut_text(team, date_str, game, result, today, yesterday):
    lines = []
    lines.append(f"{team} Lineup Leak — {date_str}")
    lines.append(f"Opponent: {game.get('opponent')}")
    lines.append(f"Status: {result.get('label')}")
    if result.get("score") is not None:
        lines.append(f"Score: {result.get('score')}/10")
    lines.append("")
    lines.append("Notes:")
    for n in result.get("notes", []):
        lines.append(f"- {n}")
    lines.append("")
    lines.append("Angles:")
    for a in result.get("angles", []):
        lines.append(f"- {a}")
    if today:
        lines.append("")
        lines.append("Today's lineup:")
        for p in today:
            lines.append(f"{p['order']}. {p['name']} {p['position']}")
    return "\n".join(lines)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
