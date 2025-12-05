from http.server import BaseHTTPRequestHandler
import json
import math

def norm(v, mini, maxi):
    try:
        v = float(v)
    except:
        v = 0.0
    if maxi - mini == 0:
        return 0.0
    return max(0.0, min(1.0, (v - mini) / (maxi - mini)))

def score_match(match):
    home = match.get("home", {}) if isinstance(match, dict) else {}
    away = match.get("away", {}) if isinstance(match, dict) else {}

    w_ht_goal_pct = 0.5
    w_shots = 0.25
    w_xg = 0.25

    home_ht_goal = norm(home.get("ht_goal_pct", 0.15), 0.0, 0.6)
    away_ht_goal = norm(away.get("ht_goal_pct", 0.12), 0.0, 0.6)

    home_shots = norm(home.get("avg_shots_ht", 0.9), 0.0, 5.0)
    away_shots = norm(away.get("avg_shots_ht", 0.8), 0.0, 5.0)

    home_xg = norm(home.get("xG_ht", 0.25), 0.0, 2.0)
    away_xg = norm(away.get("xG_ht", 0.18), 0.0, 2.0)

    home_score = w_ht_goal_pct * home_ht_goal + w_shots * home_shots + w_xg * home_xg
    away_score = w_ht_goal_pct * away_ht_goal + w_shots * away_shots + w_xg * away_xg

    raw = 1.0 - math.exp(-(home_score + away_score))
    prob = max(0.0, min(1.0, raw))

    reason = (
        f"home: ht%={home.get('ht_goal_pct',0):.2f}, shots_ht={home.get('avg_shots_ht',0):.1f}, xG_ht={home.get('xG_ht',0):.2f}; "
        f"away: ht%={away.get('ht_goal_pct',0):.2f}, shots_ht={away.get('avg_shots_ht',0):.1f}, xG_ht={away.get('xG_ht',0):.2f}"
    )

    return {"probability": round(prob, 3), "reason": reason}

class handler(BaseHTTPRequestHandler):
    def _send_json(self, status, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(content_length) if content_length > 0 else b""
        try:
            data = json.loads(raw) if raw else {}
        except Exception as e:
            return self._send_json(400, {"error": "Invalid JSON", "details": str(e)})

        matches = data.get("matches")
        if not isinstance(matches, list):
            return self._send_json(400, {"error": "Expected JSON with 'matches' array"})

        results = []
        for m in matches:
            mid = m.get("id") if isinstance(m, dict) else None
            scored = score_match(m if isinstance(m, dict) else {})
            results.append({"id": mid, "probability": scored["probability"], "reason": scored["reason"]})

        return self._send_json(200, {"results": results})

    def do_GET(self):
        self._send_json(200, {"status": "ok", "message": "API Python filtro ready. Use POST /api/filtro with JSON {matches:[...]}"})
