# scripts/spawn_peers.py  (Windows)
import sys
import time
import argparse
from pathlib import Path
import subprocess

CREATE_NEW_CONSOLE = 0x00000010  # abre uma nova janela de console por processo

def build_cmd_line(pyexe: Path, pyfile: Path, host: str, port: int, name: str,
                   peers: list[str], bootstrap: Path | None, gui: bool, title: str):
    """
    Executa via cmd.exe para poder setar o título da janela e rodar python/pythonw.
    /k mantém o console aberto.
    """
    # interpretador: pythonw para GUI (se existir), python normal para CLI
    exe = pyexe

    # base do comando que será executado dentro do cmd
    inner = f'"{exe}" "{pyfile}" --host {host} --port {port} --name "{name}"'
    for p in peers:
        inner += f' --peer {p}'
    if bootstrap:
        inner += f' --bootstrap "{bootstrap}"'

    # título + comando
    full = ['cmd.exe', '/k', f'title {title} & {inner}']
    return full

def main():
    parser = argparse.ArgumentParser(description="Spawner de peers (Windows) abrindo janelas separadas em paralelo.")
    parser.add_argument("--count", "-n", type=int, default=5, help="Quantidade de peers (default: 5)")
    parser.add_argument("--base-port", type=int, default=6000, help="Porta inicial (default: 6000)")
    parser.add_argument("--host", default="127.0.0.1", help="Host para todos os peers")
    parser.add_argument("--mode", choices=["chain", "star"], default="chain",
                        help="Topologia: chain (cadeia) ou star (estrela).")
    parser.add_argument("--gui", action="store_true", help="Usar peer_gui.py (Tkinter). Se ausente, usa peer.py")
    parser.add_argument("--bootstrap", help="Arquivo peers.json (opcional)")
    parser.add_argument("--delay", type=float, default=0.0, help="Atraso entre aberturas (s). Use 0 para simultâneo.")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]  # raiz do projeto
    pyfile = root / "src" / ("peer_gui.py" if args.gui else "peer.py")
    if not pyfile.exists():
        print(f"[ERRO] Arquivo não encontrado: {pyfile}")
        return

    # escolher python/pythonw
    pyexe = Path(sys.executable).with_name("pythonw.exe") if args.gui else Path(sys.executable)
    if args.gui and not pyexe.exists():
        # fallback se não houver pythonw.exe
        pyexe = Path(sys.executable)

    # resolver bootstrap (se houver)
    bootstrap_abs = None
    if args.bootstrap:
        b = Path(args.bootstrap)
        bootstrap_abs = (b if b.is_absolute() else (root / b)).resolve()
        if not bootstrap_abs.exists():
            print(f"[WARN] Bootstrap não encontrado: {bootstrap_abs}")
            bootstrap_abs = None

    ports = [args.base_port + i for i in range(args.count)]
    names = [f"Peer{p}" for p in ports]

    procs = []
    for i, port in enumerate(ports):
        # Peers a conectar (cadeia ou estrela)
        peers_params = []
        if args.mode == "chain" and i > 0:
            peers_params.append(f"{args.host}:{ports[i-1]}")
        elif args.mode == "star" and i > 0:
            peers_params.append(f"{args.host}:{ports[0]}")

        title = f"{'GUI' if args.gui else 'CLI'} - {names[i]} ({args.host}:{port})"

        cmd = build_cmd_line(
            pyexe=pyexe, pyfile=pyfile, host=args.host, port=port, name=names[i],
            peers=peers_params, bootstrap=bootstrap_abs, gui=args.gui, title=title
        )

        # abre cada peer em uma NOVA janela, sem bloquear
        p = subprocess.Popen(cmd, creationflags=CREATE_NEW_CONSOLE)
        procs.append(p)

        if args.delay > 0:
            time.sleep(args.delay)

    print(f"[SPAWNER] {len(procs)} janelas abertas. Para encerrar, feche cada janela ou use 'sair' nelas.")

if __name__ == "__main__":
    main()
