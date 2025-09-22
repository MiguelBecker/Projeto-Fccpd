import socket
import threading
import argparse
from common import send_msg, recv_msg, generate_msg


class Peer:
    def __init__(self, host: str, port: int, known_peers=None):
        self.host = host
        self.port = port
        self.known_peers = known_peers if known_peers else []
        self.connections = []
        self.lock = threading.Lock()
        self.seen_msgs = set()

    def start(self):
        threading.Thread(target=self._start_server, daemon=True).start()

        for peer_host, peer_port in self.known_peers:
            self.connect_to_peer(peer_host, peer_port)

        self._input_loop()

    def _start_server(self):
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.bind((self.host, self.port))
        srv.listen()
        print(f"[SERVIDOR] Peer ouvindo em {self.host}:{self.port}")

        while True:
            conn, addr = srv.accept()
            print(f"[SERVIDOR] Conexão de {addr}")
            with self.lock:
                self.connections.append(conn)
            threading.Thread(target=self._handle_peer, args=(conn,), daemon=True).start()

    def connect_to_peer(self, host, port):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((host, port))
            print(f"[CLIENTE] Conectado a {host}:{port}")
            with self.lock:
                self.connections.append(s)
            threading.Thread(target=self._handle_peer, args=(s,), daemon=True).start()
        except Exception as e:
            print(f"[ERRO] Não conectou a {host}:{port} -> {e}")

    def _handle_peer(self, conn):
        while True:
            msg = recv_msg(conn)
            if not msg:
                break
            msg_id = msg.get("id")

            if msg_id in self.seen_msgs:
                continue

            self.seen_msgs.add(msg_id)

            print(f"[RECEBIDO] {msg}")

            self.broadcast(msg, exclude=conn)

        conn.close()

    def _input_loop(self):
        while True:
            text = input("Digite mensagem ('sair' para encerrar): ")
            if text.strip().lower() == "sair":
                break
            msg = generate_msg("msg", f"{self.host}:{self.port}", text)
            self.seen_msgs.add(msg["id"])
            self.broadcast(msg)

    def broadcast(self, msg, exclude=None):
        with self.lock:
            for conn in list(self.connections):
                if conn == exclude:
                    continue
                try:
                    send_msg(conn, msg)
                except Exception as e:
                    print(f"[ERRO envio] {e}")
                    conn.close()
                    self.connections.remove(conn)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--peer", action="append", help="host:port de peer conhecido")
    parser.add_argument("--bootstrap", help="arquivo JSON com peers (descoberta)")

    args = parser.parse_args()

    known_peers = []
    if args.peer:
        for p in args.peer:
            host, port = p.split(":")
            known_peers.append((host, int(port)))

    if args.bootstrap:
        try:
            from discovery import load_peers_from_file
            known_peers.extend(load_peers_from_file(args.bootstrap))
        except Exception as e:
            print(f"[ERRO] Falha ao carregar bootstrap: {e}")

    peer = Peer(args.host, args.port, known_peers)
    peer.start()
