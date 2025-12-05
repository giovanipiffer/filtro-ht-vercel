# api/check_key.py
# Endpoint de diagnóstico — não revela a chave, apenas informa se ela existe e testa um call simples (sem expor a chave)
import os
import requests
from flask import Flask, jsonify

app = Flask(__name__)

@app.route("/", methods=["GET"])
def check_key():
    api_key = os.environ.get("API_FOOTBALL_KEY")
    present = bool(api_key)
    host = os.environ.get("API_FOOTBALL_HOST", "v3.football.api-sports.io")
    # vamos tentar um GET simples apenas para ver qual é o comportamento (capturamos status/text)
    info = {"api_key_present": present, "api_host": host}
    if not present:
        info["note"] = "API_FOOTBALL_KEY not set in environment on this runtime."
        return jsonify(info), 200
    try:
        # não enviamos a chave na resposta — apenas executamos a requisição e retornamos status/text (texto curto)
        headers = {"x-apisports-key": "REDACTED_IF_PRESENT"}
        r = requests.get(f"https://{host}/fixtures?date=2024-12-03", headers=headers, timeout=10)
        info["external_status"] = r.status_code
        # return only first 200 characters of body to avoid huge dumps and not leak key
        info["external_body_snippet"] = (r.text or "")[:200]
    except Exception as e:
        info["external_error"] = str(e)
    return jsonify(info), 200
