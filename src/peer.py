# src/peer.py
import socket
import threading
import argparse
import time
from multiprocessing import Queue
from common import send_msg, recv_msg, generate_msg
from logger_proc import LoggerProcess


class Peer:
    def __init__(self, host: str, port: int, known_peers=None, name: str = None):
        self.host = host
        self.port = port
        self.name = name or f"{host}:{port}"
        self.known_peers = known_peers if known_peers else []
        self.connections = []           # sockets ativos
        self.lock = threading.Lock()
        self.seen_msgs = set()

        # ---- IPC: fila para processo de logging
        self.log_q = Queue()
        self.logger = LoggerProcess(self.log_q, log_path=f"logs/peer_{self.port}.jsonl")
        self.logger.start()

    # -------- infra de log (publica em processo filho) --------
    def log(self, kind: str, payload: dict):
        evt = {
            "ts": time.time(),
            "peer": self.name,
            "kind": kind,          # connect, recv, send, error, info
            "data": payload
        }
        try:
            self.log_q.put_nowait(evt)
        except Exception:
            pass

    def start(self):
        threading.Thread(target=self._start_server, daemon=True).start()
        for peer_host, peer_port in self.known_peers:
            self.connect_to_peer(peer_host, peer_port)
        self._input_loop()
        # encerramento limpo
        self.shutdown()

    def shutdown(self):
        # fecha conexões
        with self.lock:
            for c in list(self.connections):
                try:
                    c.close()
                except Exception:
                    pass
            self.connections.clear()
        # encerra logger (poison pill)
        try:
            self.log_q.put_nowait(None)
        except Exception:
            pass
        # não chamamos join() para não travar CLI; processo é daemon

    def _start_server(self):
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind((self.host, self.port))
        srv.listen()
        print(f"[SERVIDOR] {self.name} ouvindo em {self.host}:{self.port}")
        self.log("info", {"msg": "listening", "addr": f"{self.host}:{self.port}"})

        while True:
            conn, addr = srv.accept()
            print(f"[SERVIDOR] conexão de {addr}")
            self.log("connect", {"from": f"{addr[0]}:{addr[1]}"})
            with self.lock:
                self.connections.append(conn)
            threading.Thread(target=self._handle_peer, args=(conn,), daemon=True).start()

    def connect_to_peer(self, host, port):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((host, port))
            print(f"[CLIENTE] Conectado a {host}:{port}")
            self.log("connect", {"to": f"{host}:{port}"})
            with self.lock:
                self.connections.append(s)
            threading.Thread(target=self._handle_peer, args=(s,), daemon=True).start()
        except Exception as e:
            print(f"[ERRO] Não conectou a {host}:{port} -> {e}")
            self.log("error", {"op": "connect", "to": f"{host}:{port}", "err": str(e)})

    def _handle_peer(self, conn):
        while True:
            msg = recv_msg(conn)
            if not msg:
                break
            msg_id = msg.get("id")

            if msg_id in self.seen_msgs:
                continue  # dup → descarta

            self.seen_msgs.add(msg_id)
            self.log("recv", {"id": msg_id, "sender": msg.get("sender"), "payload": msg.get("payload")})
            print(f"[RECEBIDO] {msg}")

            # repassa para outros (exceto quem enviou)
            self.broadcast(msg, exclude=conn)

        try:
            conn.close()
        finally:
            with self.lock:
                if conn in self.connections:
                    self.connections.remove(conn)

    def _input_loop(self):
        while True:
            text = input("Digite mensagem ('sair' para encerrar): ").strip()
            if text.lower() == "sair":
                break
            msg = generate_msg("msg", self.name, text)
            self.seen_msgs.add(msg["id"])  # marca antes de enviar
            self.log("send", {"id": msg["id"], "payload": text})
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
                    self.log("error", {"op": "send", "id": msg.get("id"), "err": str(e)})
                    try:
                        conn.close()
                    except Exception:
                        pass
                    self.connections.remove(conn)


if __name__ == "__main__":
    import sys
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--peer", action="append", help="host:port de peer conhecido")
    parser.add_argument("--bootstrap", help="arquivo JSON com peers")
    parser.add_argument("--name", help="apelido deste peer")
    args = parser.parse_args()

    known_peers = []
    if args.peer:
        for p in args.peer:
            h, pr = p.split(":")
            known_peers.append((h, int(pr)))

    if args.bootstrap:
        try:
            from discovery import load_peers_from_file
            known_peers.extend(load_peers_from_file(args.bootstrap))
        except Exception as e:
            print(f"[ERRO] bootstrap: {e}")

    peer = Peer(args.host, args.port, known_peers, name=args.name)
    try:
        peer.start()
    except KeyboardInterrupt:
        pass
    finally:
        peer.shutdown()
