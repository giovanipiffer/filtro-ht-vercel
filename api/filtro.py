# api_old/filtro.py
# Flask app para /api/filtro — busca dados da API-Football, calcula %HT, avg shots HT e xG (proxy)
# Requer: requests, flask
# A chave da API deve estar em env var: API_FOOTBALL_KEY

import os
import math
from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

API_KEY = os.environ.get("API_FOOTBALL_KEY")
API_HOST = os.environ.get("API_FOOTBALL_HOST", "v3.football.api-sports.io")
BASE = f"https://{API_HOST}"

if not API_KEY:
    # não interrompe o processo — apenas logará erro nas requisições
    app.logger.warning("API_FOOTBALL_KEY não definida nas variáveis de ambiente.")

def fetcher(path, params=None, timeout=15):
    params = params or {}
    url = BASE + path
    headers = {"x-apisports-key": API_KEY} if API_KEY else {}
    r = requests.get(url, params=params, headers=headers, timeout=timeout)
    r.raise_for_status()
    return r.json()

def get_fixtures_by_date(date):
    r = fetcher("/fixtures", {"date": date})
    return r.get("response") or r.get("data") or []

def get_last_fixtures_for_team(team_id, last=10):
    r = fetcher("/fixtures", {"team": str(team_id), "last": str(last)})
    return r.get("response") or r.get("data") or []

def get_statistics_for_fixture(fixture_id):
    try:
        r = fetcher("/fixtures/statistics", {"fixture": str(fixture_id)})
        return r.get("response") or r.get("data") or []
    except Exception:
        return []

def compute_ht_goal_pct_from_last_fixtures(last_fixtures, team_id):
    if not isinstance(last_fixtures, list) or len(last_fixtures) == 0:
        return 0.0
    count = 0
    total = 0
    for f in last_fixtures:
        score = f.get("score") or f.get("goals") or f
        htHome = htAway = None
        if score and isinstance(score, dict):
            halftime = score.get("halftime") or score.get("ht")
            if halftime:
                htHome = halftime.get("home")
                htAway = halftime.get("away")
        is_home = False
        teams = f.get("teams") or {}
        if teams:
            try:
                is_home = int(teams.get("home", {}).get("id") or 0) == int(team_id)
            except Exception:
                is_home = False
        ht_goals = (htHome if is_home else htAway) or 0
        if ht_goals > 0:
            count += 1
        total += 1
    return (count / total) if total else 0.0

def estimate_avg_shots_ht_from_fixtures(last_fixtures, team_id):
    if not isinstance(last_fixtures, list) or len(last_fixtures) == 0:
        return 0.0
    sum_shots = 0.0
    count = 0
    for f in last_fixtures:
        # se o endpoint já trouxe statistics embutido
        stats_list = f.get("statistics") or []
        if stats_list and isinstance(stats_list, list):
            team_stats = None
            for s in stats_list:
                tid = s.get("team", {}).get("id") if isinstance(s.get("team"), dict) else None
                if tid and int(tid) == int(team_id):
                    team_stats = s
                    break
            if team_stats:
                stats = team_stats.get("statistics") or []
                for st in stats:
                    typ = (st.get("type") or st.get("name") or "").lower()
                    if "shot" in typ:
                        val = st.get("value")
                        if isinstance(val, (int, float)):
                            sum_shots += (val / 2.0)  # proxy: metade das finalizações no 1º tempo
                            count += 1
                            break
    return (sum_shots / count) if count else 0.0

def compute_match_percentages_and_filter(match):
    home = match.get("home", {})
    away = match.get("away", {})
    home_pct = float(home.get("ht_goal_pct") or 0)
    away_pct = float(away.get("ht_goal_pct") or 0)
    home_shots = float(home.get("avg_shots_ht") or 0)
    away_shots = float(away.get("avg_shots_ht") or 0)
    home_xg = float(home.get("xG_ht") or 0)
    away_xg = float(away.get("xG_ht") or 0)

    max_pct = max(home_pct, away_pct)
    total_shots = home_shots + away_shots
    avg_xg = (home_xg + away_xg) / (2 if (home_xg or away_xg) else 1)

    score = round(max_pct * 100, 2) + round(avg_xg * 10, 2) + round(total_shots, 2)
    pass_filter = (max_pct >= 0.25) or (total_shots >= 2.5 and avg_xg >= 0.2)

    match["_filter"] = {
        "pass": bool(pass_filter),
        "score": score,
        "reason": "Atende critérios (pct/xG/finaliz)" if pass_filter else "Não atende critérios",
        "derived": {
            "max_pct": max_pct,
            "total_shots": total_shots,
            "avg_xg": avg_xg,
            "home_pct": home_pct,
            "away_pct": away_pct,
            "home_shots": home_shots,
            "away_shots": away_shots,
            "home_xg": home_xg,
            "away_xg": away_xg,
        },
    }
    return match

@app.route("/api/filtro", methods=["GET", "POST"])
def api_filtro():
    # aceita GET ?date=YYYY-MM-DD&last=10 ou POST com JSON {"date":"YYYY-MM-DD","last":10}
    try:
        if request.method == "POST":
            body = request.get_json(silent=True) or {}
            date = body.get("date") or body.get("d")
            lastN = int(body.get("last", 10))
        else:
            date = request.args.get("date") or request.args.get("d")
            lastN = int(request.args.get("last") or 10)
        if not date:
            return jsonify({"error": "Parâmetro `date` obrigatório. Formato YYYY-MM-DD"}), 400
        if not API_KEY:
            return jsonify({"error": "API key não configurada. Defina API_FOOTBALL_KEY nas env vars."}), 500

        fixtures = get_fixtures_by_date(date)
        out = []
        # processa sequencialmente para economizar cota
        for f in fixtures:
            fixture_id = f.get("fixture", {}).get("id") or f.get("id")
            homeTeam = f.get("teams", {}).get("home") or f.get("home") or {}
            awayTeam = f.get("teams", {}).get("away") or f.get("away") or {}

            home_last = get_last_fixtures_for_team(homeTeam.get("id"), lastN) if homeTeam.get("id") else []
            away_last = get_last_fixtures_for_team(awayTeam.get("id"), lastN) if awayTeam.get("id") else []

            home_ht_pct = compute_ht_goal_pct_from_last_fixtures(home_last, homeTeam.get("id")) if homeTeam.get("id") else 0.0
            away_ht_pct = compute_ht_goal_pct_from_last_fixtures(away_last, awayTeam.get("id")) if awayTeam.get("id") else 0.0

            home_avg_shots_ht = estimate_avg_shots_ht_from_fixtures(home_last, homeTeam.get("id")) if homeTeam.get("id") else 0.0
            away_avg_shots_ht = estimate_avg_shots_ht_from_fixtures(away_last, awayTeam.get("id")) if awayTeam.get("id") else 0.0

            stats = get_statistics_for_fixture(fixture_id) if fixture_id else []
            home_xg_ht = away_xg_ht = 0.0
            if isinstance(stats, list) and len(stats) > 0:
                for s in stats:
                    tid = s.get("team", {}).get("id") if isinstance(s.get("team"), dict) else None
                    if not s.get("statistics"):
                        continue
                    # procurar xG
                    for st in s.get("statistics", []):
                        typ = (st.get("type") or st.get("name") or "").lower()
                        val = st.get("value")
                        if "xg" in typ and isinstance(val, (int, float)):
                            if int(tid) == int(homeTeam.get("id")):
                                home_xg_ht = float(val)
                            if int(tid) == int(awayTeam.get("id")):
                                away_xg_ht = float(val)
                    # fallback: shots -> dividir por 2
                    if not home_xg_ht or not away_xg_ht:
                        for st in s.get("statistics", []):
                            typ = (st.get("type") or st.get("name") or "").lower()
                            val = st.get("value")
                            if "shot" in typ and isinstance(val, (int, float)):
                                if int(tid) == int(homeTeam.get("id")):
                                    home_xg_ht = home_xg_ht or (float(val) / 2.0)
                                if int(tid) == int(awayTeam.get("id")):
                                    away_xg_ht = away_xg_ht or (float(val) / 2.0)

            match_obj = {
                "id": fixture_id or f.get("id") or f"{homeTeam.get('id')}-{awayTeam.get('id')}-{date}",
                "date": date,
                "league": f.get("league"),
                "home": {
                    "id": homeTeam.get("id"),
                    "name": homeTeam.get("name"),
                    "ht_goal_pct": round(home_ht_pct, 4),
                    "avg_shots_ht": round(home_avg_shots_ht, 2),
                    "xG_ht": round(home_xg_ht, 4),
                },
                "away": {
                    "id": awayTeam.get("id"),
                    "name": awayTeam.get("name"),
                    "ht_goal_pct": round(away_ht_pct, 4),
                    "avg_shots_ht": round(away_avg_shots_ht, 2),
                    "xG_ht": round(away_xg_ht, 4),
                },
                "raw": f,
            }

            out.append(compute_match_percentages_and_filter(match_obj))

        # ordenar por score descendente
        out = sorted(out, key=lambda x: x.get("_filter", {}).get("score", 0), reverse=True)
        return jsonify(out)
    except requests.HTTPError as he:
        app.logger.exception("Erro HTTP ao chamar API externa")
        return jsonify({"error": "Erro ao acessar API externa", "detail": str(he)}), 502
    except Exception as e:
        app.logger.exception("Erro interno /api/filtro")
        return jsonify({"error": "Erro interno", "detail": str(e)}), 500

# entrypoint para servidores WSGI/hosting que usam this file directly
if __name__ == "__main__":
    # roda localmente para testes
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 3000)), debug=True)
