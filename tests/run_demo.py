"""
Demo automatica: inicia servidor em background, conecta 2 clientes
que enviam comandos, e verifica se o servidor processa tudo sem erros.
"""
import socket
import threading
import time
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from shared.protocol import encode, decode, recv_message, CMD_JOIN, CMD_FLIP, CMD_QUIT, CMD_GAME_START, CMD_YOUR_TURN, CMD_OK

HOST = "127.0.0.1"
PORT = 9000


def play_as(name, flips, results):
    """Cliente automatico: conecta, espera o jogo, envia flips."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)
        sock.connect((HOST, PORT))
        sock.sendall(encode(CMD_JOIN, name))

        # Aguarda GAME_START
        while True:
            raw = recv_message(sock)
            if raw is None:
                results[name] = "ERRO: conexao perdida"
                sock.close()
                return
            command, arg, payload = decode(raw)
            if command == CMD_GAME_START:
                print(f"  [DEMO] {name}: jogo iniciado!")
                break
            elif command == CMD_OK and arg == "WAITING":
                print(f"  [DEMO] {name}: aguardando oponente...")

        # Envia flips (so quando for sua vez)
        flip_count = 0
        while flip_count < len(flips):
            raw = recv_message(sock)
            if raw is None:
                break
            command, arg, payload = decode(raw)
            if command == CMD_YOUR_TURN:
                pos = flips[flip_count]
                sock.sendall(encode(CMD_FLIP, str(pos)))
                print(f"  [DEMO] {name}: FLIP {pos}")
                flip_count += 1

        sock.sendall(encode(CMD_QUIT))
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
    time.sleep(1)

    results = {}
    flips_alice = [0, 8, 1, 9, 2, 10]
    flips_bob   = [3, 11, 4, 12, 5, 13]

    try:
        print("[DEMO] Conectando Alice e Bob...")
        t1 = threading.Thread(target=play_as, args=("Alice", flips_alice, results))
        t2 = threading.Thread(target=play_as, args=("Bob", flips_bob, results))
        t1.start()
        t2.start()
        t1.join(timeout=30)
        t2.join(timeout=30)

        print("\n[DEMO] Resultados:")
        all_ok = True
        for name, result in results.items():
            status = "OK" if result == "OK" else f"FALHA: {result}"
            print(f"  {name}: {status}")
            if result != "OK":
                all_ok = False

        if all_ok:
            print("\n[DEMO] Teste automatizado concluido com sucesso!")
        else:
            print("\n[DEMO] Teste automatizado falhou!")
    finally:
        proc.terminate()
        proc.wait(timeout=5)
        print("[DEMO] Servidor encerrado.")


if __name__ == "__main__":
    main()
