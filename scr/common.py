import json
import struct
import socket
import uuid
from typing import Optional, Dict



def send_msg(sock: socket.socket, msg: Dict):
    """
    Envia um dicionário como mensagem JSON via socket,
    usando framing (4 bytes big-endian com tamanho da mensagem).
    """
    data = json.dumps(msg).encode("utf-8")
    length = struct.pack("!I", len(data))
    sock.sendall(length + data)


def recv_msg(sock: socket.socket) -> Optional[Dict]:
    """
    Recebe mensagem com framing (4 bytes + JSON).
    Retorna um dict ou None se a conexão for fechada.
    """
    header = _recvall(sock, 4)
    if not header:
        return None

    length = struct.unpack("!I", header)[0]
    data = _recvall(sock, length)
    if not data:
        return None

    return json.loads(data.decode("utf-8"))


def _recvall(sock: socket.socket, n: int) -> Optional[bytes]:
    """Lê exatamente n bytes do socket, ou None se desconectar."""
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            return None
        buf += chunk
    return buf



def generate_msg(msg_type: str, sender: str, payload: str) -> Dict:
    """
    Cria um envelope de mensagem padronizado com ID único.
    """
    return {
        "id": uuid.uuid4().hex,
        "type": msg_type,
        "sender": sender,
        "payload": payload
    }
