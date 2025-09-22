# src/logger_proc.py
import json
import os
import time
from multiprocessing import Process, Queue
from typing import Optional

class LoggerProcess(Process):
    """
    Processo dedicado a logging.
    Recebe eventos via multiprocessing.Queue (IPC) e escreve 1 evento por linha (JSONL).
    """
    def __init__(self, queue: Queue, log_path: str, rotate_mb: int = 5):
        super().__init__(daemon=True)
        self.queue = queue
        self.log_path = log_path
        self.rotate_bytes = rotate_mb * 1024 * 1024
        self._running = True

    def run(self):
        os.makedirs(os.path.dirname(self.log_path), exist_ok=True)
        f = open(self.log_path, "a", encoding="utf-8")
        try:
            while self._running:
                evt: Optional[dict] = self.queue.get()  # bloqueante
                if evt is None:      # poison pill → encerrar
                    break
                line = json.dumps(evt, ensure_ascii=False)
                f.write(line + "\n")
                f.flush()
                # rotação simples por tamanho
                if f.tell() >= self.rotate_bytes:
                    f.close()
                    ts = int(time.time())
                    os.replace(self.log_path, f"{self.log_path}.{ts}.jsonl")
                    f = open(self.log_path, "a", encoding="utf-8")
        finally:
            try:
                f.close()
            except Exception:
                pass
