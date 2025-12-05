import os
import json
import datetime
import requests
from bs4 import BeautifulSoup
from urllib.parse import parse_qs

HEADERS = {"User-Agent": "ht_filter_ready/1.0 (+https://example)"}
FOOTBALLDATA_KEY = os.getenv("FOOTBALLDATA_KEY", "").strip()

def get_todays_matches_footballdata():
    if not FOOTBALLDATA_KEY:
        return []
    today = datetime.date.today().isoformat()
    url = f"https://api.football-data.org/v2/matches?dateFrom={today}&dateTo={today}"
    headers = {"X-Auth-Token": FOOTBALLDATA_KEY}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()
        data = r.json()
        matches = []
        for m in data.get('matches', []):
            matches.append({
                "id": m.get('id'),
                "league": m.get('competition', {}).get('name'),
                "home": m.get('homeTeam', {}).get('name'),
                "away": m.get('awayTeam', {}).get('name'),
                "time": m.get('utcDate')
            })
        return matches
    except Exception as e:
        print("Football-Data API error:", e)
        return []

def get_todays_matches_worldfootball():
    try:
        today = datetime.date.today().strftime("%Y_%m_%d")
        url = f"https://www.worldfootball.net/schedule/{today}/"
        r = requests.get(url, headers=HEADERS, timeout=10)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        matches = []
        for table in soup.find_all("table"):
            for tr in table.find_all("tr"):
                tds = tr.find_all("td")
                if len(tds) >= 3:
                    for td in tds:
                        txt = td.get_text(" ", strip=True)
                        if " - " in txt and txt.count("-") >= 1:
                            parts = txt.split(" - ")
                            home = parts[0].strip()
                            away = parts[1].strip()
                            matches.append({
                                "id": None,
                                "league": None,
                                "home": home,
                                "away": away,
                                "time": None
                            })
                            break
        # remove duplicados
        seen = set()
        out = []
        for m in matches:
            key = (m["home"].lower(), m["away"].lower())
            if key not in seen:
                out.append(m)
                seen.add(key)
        return out
    except Exception as e:
        print("Scraping error:", e)
        return []

def get_todays_matches():
    api_matches = get_todays_matches_footballdata()
    if api_matches:
        return {"source": "football-data", "matches": api_matches}
    scrap_matches = get_todays_matches_worldfootball()
    if scrap_matches:
        return {"source": "worldfootball", "matches": scrap_matches}
    # fallback
    return {
        "source": "sample",
        "matches": [
            {"league": "Example", "home": "Team A", "away": "Team B"},
            {"league": "Example", "home": "Team C", "away": "Team D"}
        ]
    }

def evaluate_pre_game(home, away):
    # avaliação simples só para demonstrar o fluxo:
    score = 0
    reasons = []

    if len(home) >= 4:
        score += 1
        reasons.append("home_name_ok")

    if len(away) >= 4:
        score += 1
        reasons.append("away_name_ok")

    return {"score": score, "reasons": reasons}

def handler(request, context):
    qs = parse_qs(request.get("queryString") or "")
    min_score = int(qs.get("min_score", [1])[0])

    data = get_todays_matches()
    matches = data["matches"]

    promising = []

    for g in matches:
        home = g.get("home")
        away = g.get("away")
        pre = evaluate_pre_game(home, away)

        if pre["score"] >= min_score:
            promising.append({
                "match": g,
                "pre": pre
            })

    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({
            "source": data["source"],
            "total": len(matches),
            "promising": promising
        }, ensure_ascii=False)
    }
