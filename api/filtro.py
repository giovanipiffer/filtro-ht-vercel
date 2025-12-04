import json
from urllib.parse import parse_qs

def handler(request, context):
    query = parse_qs(request['queryString'] or "")

    data = query.get("data", [""])[0]
    liga = query.get("liga", [""])[0]
    min_odds = query.get("min_odds", ["1.80"])[0]

    resultado = {
        "data_recebida": data,
        "liga_recebida": liga,
        "min_odds": min_odds,
        "jogos_filtrados": [
            {"home": "Time A", "away": "Time B", "prob_ht": "72%"},
            {"home": "Time C", "away": "Time D", "prob_ht": "69%"}
        ]
    }

    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(resultado)
    }
