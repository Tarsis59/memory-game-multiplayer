"""
Demo automatica: inicia servidor em background, conecta 2 clientes
que jogam uma partida completa, e verifica se o servidor processa tudo.
"""
import socket
import threading
import time
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from shared.protocol import (
    encode, decode, ProtocolReader,
    CMD_JOIN, CMD_FLIP, CMD_QUIT, CMD_GAME_START,
    CMD_YOUR_TURN, CMD_OK, CMD_GAME_OVER,
)

HOST = "127.0.0.1"
PORT = 9000


def play_as(name, flips, results):
    """Cliente automatico: conecta, espera YOUR_TURN, joga DUAS cartas, repete."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)
        sock.connect((HOST, PORT))
        sock.sendall(encode(CMD_JOIN, name))
        reader = ProtocolReader()

        # Aguarda GAME_START
        while True:
            raw = reader.recv_message(sock)
            if raw is None:
                results[name] = "ERRO: conexao perdida"
                sock.close()
                return
            command, arg, payload = decode(raw)
            if command == CMD_GAME_START:
                break

        # Joga: em cada YOUR_TURN, faz 2 FLIPs
        flip_idx = 0
        while flip_idx < len(flips):
            raw = reader.recv_message(sock)
            if raw is None:
                break
            command, arg, payload = decode(raw)
            if command == CMD_GAME_OVER:
                break
            if command == CMD_YOUR_TURN:
                try:
                    sock.sendall(encode(CMD_FLIP, str(flips[flip_idx])))
                    flip_idx += 1
                    time.sleep(0.1)
                    sock.sendall(encode(CMD_FLIP, str(flips[flip_idx])))
                    flip_idx += 1
                except OSError:
                    break

        try:
            sock.sendall(encode(CMD_QUIT))
        except OSError:
            pass
        time.sleep(0.2)
        sock.close()
        results[name] = "OK"
    except Exception as e:
        results[name] = f"ERRO: {e}"


def main():
    import subprocess
    server_dir = os.path.join(os.path.dirname(__file__), "..", "server")
    print("[DEMO] Iniciando servidor...")
    proc = subprocess.Popen(
        [sys.executable, "server.py"],
        cwd=server_dir,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    time.sleep(1.5)

    results = {}
    flips_Ylo = [0, 8, 3, 11, 6, 14]
    flips_Tarsis   = [1, 9, 4, 12, 7, 15]

    try:
        print("[DEMO] Conectando Ylo e Tarsis...")
        t1 = threading.Thread(target=play_as, args=("Ylo", flips_Ylo, results))
        t2 = threading.Thread(target=play_as, args=("Tarsis", flips_Tarsis, results))
        t1.start()
        t2.start()
        t1.join(timeout=30)
        t2.join(timeout=30)

        all_ok = True
        print()
        for name, result in results.items():
            status = "OK" if result == "OK" else f"FALHA: {result}"
            print(f"  {name}: {status}")
            if result != "OK":
                all_ok = False

        if all_ok:
            print("\n[DEMO] >>> Teste automatizado concluido com sucesso! <<<")
        else:
            print("\n[DEMO] >>> Teste automatizado falhou! <<<")
    finally:
        proc.terminate()
        proc.wait(timeout=5)
        print("[DEMO] Servidor encerrado.")


if __name__ == "__main__":
    main()
