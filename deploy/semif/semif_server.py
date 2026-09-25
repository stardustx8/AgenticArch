"""SemIf decision server: loads the model once, answers typed choices over a Unix socket.

Runs inside the ai-lab/private-semif container with --network none. Protocol (HTTP/1.1
over the socket):
  GET  /health                  -> {"ok": true, "model": {...}}
  POST /v1/decide  {"state", "question", "options": [{"id", "description"}]}
                                -> SemIf direct result (option_ids, probabilities, ...)
One request at a time (single GPU model); stdlib only besides SemIf itself.
"""
import argparse
import json
import os
import socketserver
import threading
from http.server import BaseHTTPRequestHandler

from semif_phase1.core import load_causal_model, validate_row
from semif_phase1.direct import score

LOCK = threading.Lock()
STATE: dict = {}


class Handler(BaseHTTPRequestHandler):
    def address_string(self):          # Unix sockets have no client address.
        return 'unix'

    def log_message(self, fmt, *args):
        pass

    def _send(self, code: int, body: dict) -> None:
        data = json.dumps(body, allow_nan=False).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == '/health':
            self._send(200, {'ok': True, 'model': STATE['metadata']})
        else:
            self._send(404, {'error': 'not found'})

    def do_POST(self):
        if self.path != '/v1/decide':
            self._send(404, {'error': 'not found'})
            return
        try:
            n = int(self.headers.get('Content-Length', '0'))
            if not 0 < n <= 1_000_000:
                raise ValueError('bad length')
            req = json.loads(self.rfile.read(n))
            row = {'id': str(req.get('id', 'q')), 'state': req['state'],
                   'question': req['question'], 'options': req['options']}
            validate_row(row)
            with LOCK:
                result = score(STATE['model'], STATE['tokenizer'], row, STATE['metadata'],
                               STATE['max_tokens'])
            self._send(200, result)
        except (ValueError, KeyError, TypeError) as exc:
            self._send(400, {'error': str(exc)[:500]})


class UnixHTTPServer(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    daemon_threads = True


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--socket', required=True)
    ap.add_argument('--model', required=True)
    ap.add_argument('--revision', default='local')
    ap.add_argument('--max-tokens', type=int, default=4096)
    a = ap.parse_args()
    model, tokenizer, metadata = load_causal_model(a.model, a.revision)
    STATE.update(model=model, tokenizer=tokenizer, metadata=metadata, max_tokens=a.max_tokens)
    if os.path.exists(a.socket):
        os.unlink(a.socket)
    server = UnixHTTPServer(a.socket, Handler)
    os.chmod(a.socket, 0o600)
    print('SemIf server ready on', a.socket, flush=True)
    server.serve_forever()


if __name__ == '__main__':
    main()
