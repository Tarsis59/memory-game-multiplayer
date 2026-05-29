"""
Teste integracao: Alice (1o jogador) faz 2 FLIPs, verifica MATCH ou NO_MATCH.
"""
import subprocess
import socket
import threading
import time
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from shared.protocol import (
    encode, decode, recv_message,
    CMD_JOIN, CMD_FLIP,
    CMD_GAME_START, CMD_YOUR_TURN, CMD_WAIT_TURN,
    CMD_CARD_REVEALED, CMD_MATCH, CMD_NO_MATCH,
)

HOST = "127.0.0.1"
PORT = 9000


def dummy_player(name):
    """Segundo jogador: conecta e aguarda eventos."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(15)
    sock.connect((HOST, PORT))
    sock.sendall(encode(CMD_JOIN, name))
    try:
        while True:
            raw = recv_message(sock)
            if raw is None:
                break
    except:
        pass
    sock.close()


def test():
    # Inicia Alice, depois Bob
    alice = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    alice.settimeout(10)
    alice.connect((HOST, PORT))
    alice.sendall(encode(CMD_JOIN, "Alice"))

    bob = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    bob.settimeout(10)
    bob.connect((HOST, PORT))
    bob.sendall(encode(CMD_JOIN, "Bob"))

    # Alice aguarda GAME_START (ignora OK WAITING)
    while True:
        raw = recv_message(alice)
        assert raw is not None
        cmd, _, _ = decode(raw)
        if cmd == CMD_GAME_START:
            break

    # Alice aguarda YOUR_TURN (deve receber, e a primeira)
    raw = recv_message(alice)
    assert raw is not None
    cmd, _, _ = decode(raw)
    assert cmd == CMD_YOUR_TURN, f"Alice esperava YOUR_TURN, recebeu {cmd}"

    # 1o FLIP de Alice
    alice.sendall(encode(CMD_FLIP, "0"))
    raw = recv_message(alice)
    assert raw is not None
    cmd1, _, p1 = decode(raw)
    assert cmd1 == CMD_CARD_REVEALED, f"Esperava CARD_REVEALED, recebeu {cmd1}"

    # 2o FLIP de Alice (MESMO turno)
    alice.sendall(encode(CMD_FLIP, "8"))
    raw = recv_message(alice)
    assert raw is not None
    cmd2, _, p2 = decode(raw)
    # Pode ser CARD_REVEALED seguido de MATCH/NO_MATCH
    if cmd2 == CMD_CARD_REVEALED:
        raw = recv_message(alice)
        assert raw is not None
        cmd2, _, p2 = decode(raw)
    assert cmd2 in (CMD_MATCH, CMD_NO_MATCH), f"Esperava MATCH/NO_MATCH, recebeu {cmd2}"
    print(f"  2 FLIPs -> resultado: {cmd2}")

    alice.close()
    bob.close()
    return True


def main():
    print("[TEST] Iniciando servidor...")
    server_dir = os.path.join(os.path.dirname(__file__), "..", "server")
    proc = subprocess.Popen(
        [sys.executable, "server.py"],
        cwd=server_dir,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    time.sleep(1)

    try:
        ok = test()
        if ok:
            print("[TEST] >>> PASSOU! Alice fez 2 FLIPs e recebeu MATCH/NO_MATCH! <<<")
        else:
            print("[TEST] >>> FALHOU <<<")
    finally:
        proc.terminate()
        proc.wait()


if __name__ == "__main__":
    main()
