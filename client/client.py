"""
Cliente do Jogo da Memoria Multiplayer - MGAME/1.0
Execute duas vezes em terminais separados para jogar.
"""
import socket
import threading
import sys
import os
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from shared.protocol import (
    encode, decode, recv_message,
    CMD_JOIN, CMD_FLIP, CMD_QUIT,
    CMD_OK, CMD_ERR, CMD_GAME_START,
    CMD_YOUR_TURN, CMD_WAIT_TURN,
    CMD_CARD_REVEALED, CMD_MATCH, CMD_NO_MATCH,
    CMD_SCORE_UPDATE, CMD_GAME_OVER,
    CMD_PLAYER_LEFT, CMD_BYE,
)

HOST = "127.0.0.1"
PORT = 9000

board        = ["?"] * 16
revealed     = [False] * 16
scores       = {}
my_turn      = False
game_over    = False
my_name      = ""
board_lock   = threading.Lock()


def _clear():
    os.system("cls" if os.name == "nt" else "clear")


def render_board():
    _clear()
    print("=" * 42)
    print("   JOGO DA MEMORIA MULTIPLAYER")
    print("=" * 42)

    if scores:
        placar = "  ".join(f"{n}: {s} pts" for n, s in scores.items())
        print(f"  Placar -> {placar}")
    print()

    print("     0    1    2    3")
    print("  +----+----+----+----+")
    for row in range(4):
        cells = ""
        for col in range(4):
            pos = row * 4 + col
            val = board[pos] if revealed[pos] or board[pos] != "?" else "?"
            cells += f" {val:^3}|"
        print(f"{row} |{cells}")
        if row < 3:
            print("  +----+----+----+----+")
    print("  +----+----+----+----+")
    print()


def render_status(msg: str):
    print(f"  >> {msg}")
    print()


def receiver(sock):
    global my_turn, game_over

    while True:
        raw = recv_message(sock)
        if raw is None:
            print("\n[CLIENTE] Conexao encerrada pelo servidor.")
            game_over = True
            break

        command, arg, payload = decode(raw)

        with board_lock:

            if command == CMD_OK and arg == "WAITING":
                render_board()
                render_status("Conectado! Aguardando segundo jogador...")

            elif command == CMD_GAME_START and payload:
                board_size = payload.get("board_size", 16)
                for i in range(board_size):
                    board[i]    = "?"
                    revealed[i] = False
                players = payload.get("players", [])
                render_board()
                render_status(f"Jogo iniciado! Jogadores: {' vs '.join(players)}")
                time.sleep(1)

            elif command == CMD_YOUR_TURN:
                my_turn = True
                render_board()
                render_status("SUA VEZ! Digite a posicao (0-15):")

            elif command == CMD_WAIT_TURN:
                my_turn = False
                render_board()
                render_status(f"Vez de {arg}... aguarde.")

            elif command == CMD_CARD_REVEALED and payload:
                pos    = payload["pos"]
                symbol = payload["symbol"]
                player = payload["player"]
                board[pos] = symbol
                render_board()
                render_status(f"{player} virou posicao {pos} -> [{symbol}]")
                time.sleep(0.8)

            elif command == CMD_MATCH and payload:
                positions = payload["positions"]
                symbol    = payload["symbol"]
                player    = payload["player"]
                for pos in positions:
                    revealed[pos] = True
                    board[pos]    = symbol
                render_board()
                render_status(f"PAR! {player} encontrou [{symbol}] nas posicoes {positions}!")
                time.sleep(1.2)

            elif command == CMD_NO_MATCH and payload:
                positions = payload["positions"]
                player    = payload["player"]
                render_board()
                render_status(f"Sem par! {player} errou posicoes {positions}. Cartas viradas de volta.")
                time.sleep(1.5)
                for pos in positions:
                    board[pos] = "?"

            elif command == CMD_SCORE_UPDATE and payload:
                scores.update(payload.get("scores", {}))

            elif command == CMD_GAME_OVER and payload:
                game_over = True
                my_turn   = False
                final_scores = payload.get("scores", {})
                winner       = payload.get("winner", "?")
                scores.update(final_scores)
                render_board()
                print("=" * 42)
                print("         FIM DE JOGO!")
                print("=" * 42)
                for name, pts in final_scores.items():
                    crown = " VENCEDOR" if name == winner else ""
                    print(f"  {crown:>10} {name}: {pts} pontos")
                if winner == "EMPATE":
                    print("\n  EMPATE! Bem jogado pelos dois!")
                else:
                    print(f"\n  Vencedor: {winner}!")
                print("=" * 42)

            elif command == CMD_PLAYER_LEFT:
                game_over = True
                my_turn   = False
                render_board()
                render_status(f"{arg} abandonou o jogo. Partida encerrada.")

            elif command == CMD_ERR:
                render_board()
                render_status(f"Erro: {arg}")

            elif command == CMD_BYE:
                break


def main():
    global my_name

    if len(sys.argv) > 1:
        my_name = sys.argv[1]
    else:
        my_name = input("Digite seu apelido: ").strip()
        if not my_name:
            my_name = "Jogador"

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.connect((HOST, PORT))
    except ConnectionRefusedError:
        print(f"[CLIENTE] Nao foi possivel conectar em {HOST}:{PORT}. Servidor esta rodando?")
        return

    print(f"[CLIENTE] Conectado como '{my_name}'")

    sock.sendall(encode(CMD_JOIN, my_name))

    t = threading.Thread(target=receiver, args=(sock,), daemon=True)
    t.start()

    try:
        while not game_over:
            if my_turn:
                try:
                    entry = input().strip()
                except EOFError:
                    break
                if not entry:
                    continue
                if entry.lower() in ("quit", "sair", "q"):
                    sock.sendall(encode(CMD_QUIT))
                    break
                try:
                    pos = int(entry)
                    if 0 <= pos <= 15:
                        sock.sendall(encode(CMD_FLIP, str(pos)))
                        my_turn = False
                    else:
                        print("  Posicao invalida. Digite entre 0 e 15.")
                except ValueError:
                    print("  Digite um numero de 0 a 15.")
            else:
                time.sleep(0.1)
    except KeyboardInterrupt:
        sock.sendall(encode(CMD_QUIT))
    finally:
        sock.close()
        print("[CLIENTE] Desconectado. Ate a proxima!")


if __name__ == "__main__":
    main()
