import json
from typing import List, Tuple


def load_peers_from_file(path: str) -> List[Tuple[str, int]]:
    """
    Lê peers de um arquivo JSON no formato:
    [
      {"host": "127.0.0.1", "port": 5000},
      {"host": "127.0.0.1", "port": 5001}
    ]
    
    Retorna uma lista de tuplas: [(host, port), ...]
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return [(item["host"], int(item["port"])) for item in data]
    except FileNotFoundError:
        print(f"[DISCOVERY] Arquivo {path} não encontrado.")
        return []
    except Exception as e:
        print(f"[DISCOVERY] Erro ao ler {path}: {e}")
        return []


def save_peers_to_file(path: str, peers: List[Tuple[str, int]]):
    """
    Salva peers em arquivo JSON no formato:
    [
      {"host": "127.0.0.1", "port": 5000},
      {"host": "127.0.0.1", "port": 5001}
    ]
    """
    try:
        data = [{"host": h, "port": p} for (h, p) in peers]
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        print(f"[DISCOVERY] Peers salvos em {path}")
    except Exception as e:
        print(f"[DISCOVERY] Erro ao salvar {path}: {e}")
