# api/testar.py
# Serve uma página HTML simples para testar /api/filtro
from flask import Flask, request

app = Flask(__name__)

@app.route("/", methods=["GET"])
def page():
    html = """<!doctype html>
<html>
<head>
  <meta charset="utf-8"/>
  <title>Testar — Filtro HT</title>
  <style>
    body{font-family:Arial,Helvetica,sans-serif;max-width:980px;margin:24px auto;padding:12px}
    .card{border:1px solid #ddd;padding:12px;border-radius:8px;margin-bottom:10px}
    .pass{color:green;font-weight:700}
    .fail{color:#c00;font-weight:700}
    pre{white-space:pre-wrap;background:#f7f7f7;padding:10px;border-radius:6px;overflow:auto}
  </style>
</head>
<body>
  <h1>Testar — Filtro HT</h1>

  <div class="card">
    <label>Data: <input id="date" type="date" value="2025-12-05"/></label>
    <label style="margin-left:12px">Últimos (last):
      <select id="last">
        <option value="3">3</option>
        <option value="5" selected>5</option>
        <option value="8">8</option>
        <option value="10">10</option>
      </select>
    </label>
    <div style="margin-top:10px">
      <button id="btnFetch">Buscar jogos</button>
      <button id="btnClear">Limpar</button>
    </div>
    <div id="log" style="margin-top:8px;color:#555"></div>
  </div>

  <div id="results"></div>

  <script>
    const btn = document.getElementById('btnFetch');
    const btnClear = document.getElementById('btnClear');
    const resultsEl = document.getElementById('results');
    const logEl = document.getElementById('log');

    btn.addEventListener('click', async () => {
      const date = document.getElementById('date').value;
      const last = document.getElementById('last').value;
      if (!date) { alert('Escolha uma data'); return; }
      logEl.textContent = `Buscando ${date} (last=${last}) ...`;
      resultsEl.innerHTML = '';
      try {
        const res = await fetch(`/api/filtro?date=${date}&last=${last}`);
        if (!res.ok) {
          const txt = await res.text();
          logEl.textContent = 'Erro: ' + res.status + ' — ' + txt;
          return;
        }
        const data = await res.json();
        logEl.textContent = `Retornou ${Array.isArray(data) ? data.length : 0} itens`;
        if (!Array.isArray(data) || data.length === 0) {
          resultsEl.innerHTML = '<div class="card">Nenhum jogo encontrado para essa data.</div>';
          return;
        }
        // render simples
        data.forEach(m => {
          const pass = m._filter?.pass;
          const html = `
            <div class="card">
              <div style="display:flex;justify-content:space-between;align-items:center">
                <div><strong>${m.home?.name || 'Home'} × ${m.away?.name || 'Away'}</strong>
                <div style="color:#666;font-size:13px">pct(max): ${Number(m._filter?.derived?.max_pct||0).toFixed(3)} • shots: ${Number(m._filter?.derived?.total_shots||0).toFixed(2)} • xG: ${Number(m._filter?.derived?.avg_xg||0).toFixed(2)}</div>
                </div>
                <div style="text-align:right">
                  <div class="${pass ? 'pass' : 'fail'}">${pass ? 'PASS' : 'FAIL'}</div>
                  <div style="font-size:12px">Score: ${Number(m._filter?.score||0).toFixed(2)}</div>
                </div>
              </div>
            </div>
          `;
          resultsEl.insertAdjacentHTML('beforeend', html);
        });
      } catch (e) {
        logEl.textContent = 'Erro: ' + e;
      }
    });

    btnClear.addEventListener('click', () => {
      resultsEl.innerHTML = '';
      logEl.textContent = '';
    });
  </script>
</body>
</html>"""
    return html, 200, {"Content-Type": "text/html; charset=utf-8"}
