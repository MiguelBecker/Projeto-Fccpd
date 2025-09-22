import socket
import threading
import argparse
import time
import json
from queue import Queue, Empty
from typing import List, Tuple, Optional
from flask import Flask, Response, request, jsonify, render_template_string

from common import send_msg, recv_msg, generate_msg

class PeerCore:
    def __init__(self, host: str, port: int, known_peers: Optional[List[Tuple[str, int]]] = None, on_message=None, on_log=None):
        self.host = host
        self.port = port
        self.known_peers = known_peers or []
        self.connections: List[socket.socket] = []
        self.lock = threading.Lock()
        self.seen_msgs = set()
        self.on_message = on_message or (lambda m: None)
        self.on_log = on_log or (lambda s: None)
        self._running = True

    def start(self):
        threading.Thread(target=self._start_server, daemon=True).start()
        for peer_host, peer_port in self.known_peers:
            self.connect_to_peer(peer_host, peer_port)

    def stop(self):
        self._running = False
        with self.lock:
            for c in self.connections:
                try:
                    c.shutdown(socket.SHUT_RDWR)
                except Exception:
                    pass
                try:
                    c.close()
                except Exception:
                    pass
            self.connections.clear()

    def _start_server(self):
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind((self.host, self.port))
        srv.listen()
        self.on_log(f"[SERVIDOR] ouvindo em {self.host}:{self.port}")
        while self._running:
            try:
                conn, addr = srv.accept()
            except OSError:
                break
            self.on_log(f"[SERVIDOR] conexão de {addr}")
            with self.lock:
                self.connections.append(conn)
            threading.Thread(target=self._handle_peer, args=(conn,), daemon=True).start()
        try:
            srv.close()
        except Exception:
            pass

    def connect_to_peer(self, host, port):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((host, port))
            self.on_log(f"[CLIENTE] conectado a {host}:{port}")
            with self.lock:
                self.connections.append(s)
            threading.Thread(target=self._handle_peer, args=(s,), daemon=True).start()
        except Exception as e:
            self.on_log(f"[ERRO] não conectou a {host}:{port} -> {e}")

    def _handle_peer(self, conn):
        while self._running:
            msg = recv_msg(conn)
            if not msg:
                break
            msg_id = msg.get("id")
            if msg_id in self.seen_msgs:
                continue
            self.seen_msgs.add(msg_id)
            self.broadcast(msg, exclude=conn)
            self.on_message(msg)
        try:
            conn.close()
        except Exception:
            pass
        with self.lock:
            if conn in self.connections:
                self.connections.remove(conn)

    def send_text(self, text: str, sender_name: str):
        msg = generate_msg("msg", sender_name, text)
        self.seen_msgs.add(msg["id"])
        self.broadcast(msg)
        self.on_message(msg)

    def broadcast(self, msg, exclude=None):
        with self.lock:
            for conn in list(self.connections):
                if conn == exclude:
                    continue
                try:
                    send_msg(conn, msg)
                except Exception as e:
                    self.on_log(f"[ERRO envio] {e}")
                    try:
                        conn.close()
                    except Exception:
                        pass
                    self.connections.remove(conn)

HTML = """<!doctype html>
<html>
<head>
  <meta charset="utf-8"/>
  <title>P2P Chat — {{ name }}</title>
  <style>
    body { font-family: Consolas, monospace; background: #0b0e11; color: #c3f9c3; margin: 0; }
    header { background: #091015; padding: 10px 14px; border-bottom: 1px solid #183024; }
    .wrap { padding: 12px; }
    #log { background: #0e141a; border: 1px solid #1d3a2b; height: 60vh; overflow-y: auto; padding: 10px; white-space: pre-wrap; }
    .line { margin: 2px 0; }
    .sys { color: #8cd48c; }
    .me { color: #a5fca5; }
    .msg { color: #c3f9c3; }
    form { display: flex; gap: 8px; margin-top: 10px; }
    input[type=text] { flex: 1; padding: 8px; background: #0b1218; color: #c3f9c3; border: 1px solid #1d3a2b; }
    button { padding: 8px 12px; background: #1d3a2b; color: #c3f9c3; border: 1px solid #2b5a41; cursor: pointer; }
    button:hover { background: #24503a; }
  </style>
</head>
<body>
  <header>
    <strong>P2P Chat</strong> — Peer: {{ name }} | P2P: {{ host }}:{{ port }} | UI: http://127.0.0.1:{{ http_port }}
  </header>
  <div class="wrap">
    <div id="log"></div>
    <form id="form">
      <input id="text" type="text" placeholder="Digite sua mensagem e Enter / Enviar"/>
      <button type="submit">Enviar</button>
    </form>
  </div>
<script>
  const log = document.getElementById('log');
  function appendLine(text, cls='msg') {
    const div = document.createElement('div');
    div.className = 'line ' + cls;
    div.textContent = text;
    log.appendChild(div);
    log.scrollTop = log.scrollHeight;
  }

  // Stream de eventos (SSE)
  const es = new EventSource('/stream');
  es.onmessage = (e) => {
    try {
      const data = JSON.parse(e.data);
      if (data.type === 'log') {
        appendLine(data.payload, 'sys');
      } else if (data.type === 'msg') {
        appendLine(`[${data.sender}] ${data.payload}`, 'msg');
      }
    } catch (err) { console.error(err); }
  };
  es.onerror = () => appendLine('[SISTEMA] conexão SSE caiu. Recarregue a página.', 'sys');

  // Envio por POST
  const form = document.getElementById('form');
  const input = document.getElementById('text');
  form.addEventListener('submit', async (ev) => {
    ev.preventDefault();
    const text = input.value.trim();
    if (!text) return;
    try {
      const res = await fetch('/send', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ text }) });
      if (res.ok) {
        input.value = '';
      } else {
        appendLine('[SISTEMA] erro ao enviar.', 'sys');
      }
    } catch (e) {
      appendLine('[SISTEMA] falha de rede.', 'sys');
    }
  });

  appendLine('[SISTEMA] interface carregada.', 'sys');
</script>
</body>
</html>
"""

def create_app(core: PeerCore, ui_name: str, host: str, port: int, http_port: int):
    app = Flask(__name__)
    sse_clients: List[Queue] = []

    def push_event(evt: dict):
        for q in list(sse_clients):
            try:
                q.put_nowait(evt)
            except Exception:
                pass
    def on_message(m):
        push_event(m)

    def on_log(s):
        push_event({"type": "log", "payload": s})

    core.on_message = on_message
    core.on_log = on_log
    core.start()

    @app.route("/")
    def index():
        return render_template_string(HTML, name=ui_name, host=host, port=port, http_port=http_port)

    @app.route("/send", methods=["POST"])
    def send():
        data = request.get_json(silent=True) or {}
        text = str(data.get("text", "")).strip()
        if not text:
            return jsonify({"ok": False, "error": "empty"}), 400
        core.send_text(text, ui_name)
        return jsonify({"ok": True})

    @app.route("/stream")
    def stream():
        q = Queue()
        sse_clients.append(q)

        def gen():
            hello = {"type": "log", "payload": f"[SSE] conectado — {ui_name}"}
            yield f"data: {json.dumps(hello)}\n\n"
            try:
                while True:
                    evt = q.get()
                    yield f"data: {json.dumps(evt)}\n\n"
            except GeneratorExit:
                pass
            finally:
                try:
                    sse_clients.remove(q)
                except ValueError:
                    pass

        return Response(gen(), mimetype="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    return app


def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1", help="host P2P")
    ap.add_argument("--port", type=int, required=True, help="porta P2P (TCP sockets)")
    ap.add_argument("--http-port", type=int, required=True, help="porta HTTP da UI")
    ap.add_argument("--peer", action="append", help="host:port de peer conhecido")
    ap.add_argument("--bootstrap", help="arquivo JSON com peers (opcional)")
    ap.add_argument("--name", help="apelido exibido na UI")
    return ap.parse_args()


if __name__ == "__main__":
    args = parse_args()
    known: List[Tuple[str,int]] = []

    if args.peer:
        for p in args.peer:
            h, pr = p.split(":")
            known.append((h, int(pr)))

    if args.bootstrap:
        try:
            from discovery import load_peers_from_file
            known.extend(load_peers_from_file(args.bootstrap))
        except Exception as e:
            print(f"[ERRO] bootstrap: {e}")

    ui_name = args.name or f"{args.host}:{args.port}"
    core = PeerCore(args.host, args.port, known)

    app = create_app(core, ui_name, args.host, args.port, args.http_port)
    app.run(host="127.0.0.1", port=args.http_port, debug=False, threaded=True)
