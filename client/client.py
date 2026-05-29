"""
Cliente do Jogo da Memoria Multiplayer - MGAME/1.0
Execute duas vezes em terminais separados para jogar.
"""
import socket
import threading
import sys
import os
import time
import queue

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from shared.protocol import (
    encode, decode, ProtocolReader,
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
my_matches   = []  # (symbol, [pos1, pos2]) para cada par que este jogador encontrou
board_lock   = threading.Lock()

# Fila de entrada: thread do input coloca, main consome
input_queue = queue.Queue()


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


def input_listener():
    """Thread que le linhas do stdin e coloca na fila."""
    while not game_over:
        try:
            line = sys.stdin.readline()
            if line:
                input_queue.put(line.strip())
        except (EOFError, OSError):
            break


def receiver(sock):
    """Thread que recebe mensagens do servidor, atualiza estado E mostra prompt."""
    global my_turn, game_over, my_matches
    reader = ProtocolReader()
    receiver_flips = 0  # quantas cartas este jogador virou no turno atual

    while True:
        raw = reader.recv_message(sock)
        if raw is None:
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
                my_matches.clear()
                render_board()
                render_status(f"Jogo iniciado! Jogadores: {' vs '.join(players)}")
                receiver_flips = 0
                time.sleep(1)

            elif command == CMD_YOUR_TURN:
                my_turn = True
                receiver_flips = 0
                render_board()
                render_status(f"{my_name}, sua vez!")
                print(f"  >> {my_name}, SUA VEZ! Escolha a PRIMEIRA carta (0-15): ", flush=True)

            elif command == CMD_WAIT_TURN:
                my_turn = False
                receiver_flips = 0
                render_board()
                render_status(f"Vez de {arg}... aguarde.")

            elif command == CMD_CARD_REVEALED and payload:
                pos    = payload["pos"]
                symbol = payload["symbol"]
                player = payload["player"]
                board[pos] = symbol
                render_board()
                render_status(f"{player} escolheu posicao {pos} -> [{symbol}]")
                if player == my_name:
                    receiver_flips += 1
                    if receiver_flips == 1 and my_turn:
                        print(f"  >> Agora escolha a SEGUNDA carta (0-15): ", flush=True)

            elif command == CMD_MATCH and payload:
                positions = payload["positions"]
                symbol    = payload["symbol"]
                player    = payload["player"]
                for pos in positions:
                    revealed[pos] = True
                    board[pos]    = symbol
                render_board()
                render_status(f"PAR! {player} encontrou [{symbol}] nas posicoes {positions}!")
                if player == my_name:
                    my_matches.append((symbol, list(positions)))
                time.sleep(1)

            elif command == CMD_NO_MATCH and payload:
                positions = payload["positions"]
                player    = payload["player"]
                render_board()
                cards_str = " e ".join(f"[{board[p]}] na posicao {p}" for p in positions)
                render_status(f"{player}, suas cartas: {cards_str}")
                time.sleep(2.5)
                for pos in positions:
                    board[pos] = "?"
                render_board()
                render_status(f"Sem par! Cartas viradas. Proximo jogador.")

            elif command == CMD_SCORE_UPDATE and payload:
                scores.update(payload.get("scores", {}))

            elif command == CMD_GAME_OVER and payload:
                game_over = True
                my_turn   = False
                final_scores = payload.get("scores", {})
                winner       = payload.get("winner", "?")
                scores.update(final_scores)

                # Fase 1: revela tabuleiro completo por 2.5s
                render_board()
                render_status("Fim de jogo! Revelando todas as cartas...")
                time.sleep(2.5)

                # Fase 2: tela final com resumo das cartas
                render_board()
                print("=" * 42)
                print("         FIM DE JOGO!")
                print("=" * 42)

                # Resumo das cartas que ESTE jogador encontrou
                if my_matches:
                    print(f"\n  {my_name}, suas cartas encontradas:")
                    for symbol, poss in my_matches:
                        pos_str = " e ".join(str(p) for p in poss)
                        print(f"    [{symbol}] nas posicoes {pos_str}")
                    print()

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
                print(f"\n  [ERRO] {arg}\n")

            elif command == CMD_BYE:
                break


def main():
    global my_name, my_turn, game_over

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

    # Inicia receptor em thread separada
    t = threading.Thread(target=receiver, args=(sock,), daemon=True)
    t.start()

    # Inicia listener de input em thread separada
    inp = threading.Thread(target=input_listener, daemon=True)
    inp.start()

    # Loop principal: SOMENTE le input e envia comandos
    # Toda a saida (tabuleiro, status, prompts) fica na thread receiver
    flips_in_turn = 0

    try:
        while not game_over:
            if my_turn:
                try:
                    entry = input_queue.get(timeout=0.1)
                except queue.Empty:
                    continue

                if not entry:
                    continue
                if entry.lower() in ("quit", "sair", "q"):
                    sock.sendall(encode(CMD_QUIT))
                    break

                try:
                    pos = int(entry)
                    if 0 <= pos <= 15:
                        sock.sendall(encode(CMD_FLIP, str(pos)))
                        flips_in_turn += 1
                        if flips_in_turn >= 2:
                            my_turn = False
                            flips_in_turn = 0
                    else:
                        print("  Posicao invalida. Digite entre 0 e 15.")
                except ValueError:
                    print("  Digite um numero de 0 a 15.")
            else:
                flips_in_turn = 0
                time.sleep(0.05)

    except KeyboardInterrupt:
        sock.sendall(encode(CMD_QUIT))
    finally:
        game_over = True
        sock.close()
        print("\n[CLIENTE] Desconectado. Ate a proxima!")


if __name__ == "__main__":
    main()
