import sys
import argparse
import subprocess
import webbrowser
from pathlib import Path
import time

def main():
    ap = argparse.ArgumentParser(description="Spawner web: peers com UI em abas do navegador (Windows/Linux/Mac).")
    ap.add_argument("--count", "-n", type=int, default=3)
    ap.add_argument("--base-port", type=int, default=6000, help="porta P2P inicial")
    ap.add_argument("--base-http", type=int, default=8000, help="porta HTTP inicial")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--mode", choices=["chain","star"], default="chain")
    ap.add_argument("--delay", type=float, default=0.2, help="delay entre processos")
    args = ap.parse_args()

    root = Path(__file__).resolve().parents[1]
    pyfile = root / "src" / "peer_web.py"
    if not pyfile.exists():
        print(f"[ERRO] não encontrei {pyfile}")
        return

    ports = [args.base_port + i for i in range(args.count)]
    http_ports = [args.base_http + i for i in range(args.count)]

    procs = []
    for i in range(args.count):
        p2p_port = ports[i]
        http_port = http_ports[i]
        peers = []
        if args.mode == "chain" and i > 0:
            peers.append(f"{args.host}:{ports[i-1]}")
        elif args.mode == "star" and i > 0:
            peers.append(f"{args.host}:{ports[0]}")

        cmd = [sys.executable, str(pyfile),
               "--host", args.host,
               "--port", str(p2p_port),
               "--http-port", str(http_port),
               "--name", f"Peer{p2p_port}"]
        for peer in peers:
            cmd += ["--peer", peer]

        p = subprocess.Popen(cmd)
        procs.append(p)
        url = f"http://127.0.0.1:{http_port}"
        for _ in range(12):
            try:
                webbrowser.open_new_tab(url)
                break
            except Exception:
                time.sleep(0.2)

        time.sleep(args.delay)

    print(f"[SPAWNER] {len(procs)} peers iniciados. Abas abertas em {', '.join(map(str, http_ports))}.")

if __name__ == "__main__":
    main()
