from http.server import BaseHTTPRequestHandler
import json

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length)

        try:
            data = json.loads(body)
        except:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b'Invalid JSON')
            return

        resposta = {
            "status": "ok",
            "message": "API Python funcionando!",
            "data_recebida": data
        }

        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(resposta).encode('utf-8'))
