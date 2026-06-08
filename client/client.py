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
    CMD_PING, CMD_PONG, # NOVAS CONSTANTES
)

HOST = "127.0.0.1"
PORT = 9000

board        = ["?"] * 16
revealed     = [False] * 16
scores       = {}
my_turn      = False
game_over    = False
my_name      = ""
my_matches   = []  
board_lock   = threading.Lock()

input_queue = queue.Queue()


def _clear():
    os.system("cls" if os.name == "nt" else "clear")


# Cores ANSI
R   = "\033[0m"
VR  = "\033[92m"
VM  = "\033[91m"
AM  = "\033[93m"
AZ  = "\033[94m"
MG  = "\033[95m"
CI  = "\033[96m"
BR  = "\033[1m"

CORES_CARTAS = {
    "A": "\033[91m", "B": "\033[92m", "C": "\033[93m",
    "D": "\033[94m", "E": "\033[95m", "F": "\033[96m",
    "G": "\033[92;1m", "H": "\033[93;1m",
}

def render_board():
    _clear()
    print(f"{CI}{'=' * 42}{R}")
    print(f"{AM}   JOGO DA MEMORIA MULTIPLAYER{R}")
    print(f"{CI}{'=' * 42}{R}")

    if scores:
        placar = f"{CI}  Placar ->{R}  " + f"  {R}".join(
            f"{BR}{n}{R}: {VR}{s}{R} pts" for n, s in scores.items()
        )
        print(placar)

    revealed_count = sum(1 for r in revealed if r)
    pairs_left = 8 - revealed_count // 2
    if pairs_left > 0:
        print(f"{AM}  Pares restantes: {pairs_left}{R}")
    else:
        print(f"{VR}  Todos os pares encontrados!{R}")

    print()

    print(f"     {AZ}0{R}    {AZ}1{R}    {AZ}2{R}    {AZ}3{R}")
    print(f"  {CI}+----+----+----+----+{R}")
    for row in range(4):
        cells = ""
        for col in range(4):
            pos = row * 4 + col
            if revealed[pos] or board[pos] != "?":
                simbolo = board[pos]
                cor = CORES_CARTAS.get(simbolo, BR)
                val = f"{cor}{simbolo:^3}{R}"
            else:
                val = f" {AM}?{R} "
            cells += f"{val}|"
        print(f"{AZ}{row}{R} |{cells}")
        if row < 3:
            print(f"  {CI}+----+----+----+----+{R}")
    print(f"  {CI}+----+----+----+----+{R}")
    print()

def render_status(msg: str):
    if "PAR!" in msg or "Vencedor" in msg:
        msg = f"{VR}{msg}{R}"
    elif "erro" in msg or "Erro" in msg or "ERRO" in msg:
        msg = f"{VM}{msg}{R}"
    elif "sua vez" in msg.lower():
        msg = f"{AM}{msg}{R}"
    print(f"  >> {msg}")
    print()

def input_listener():
    while not game_over:
        try:
            line = sys.stdin.readline()
            if line:
                input_queue.put(line.strip())
        except (EOFError, OSError):
            break


def receiver(sock):
    global my_turn, game_over, my_matches
    reader = ProtocolReader()
    receiver_flips = 0

    while True:
        raw = reader.recv_message(sock)
        if raw is None:
            game_over = True
            break

        command, arg, payload = decode(raw)

        # Trata o Heartbeat silenciosamente
        if command == CMD_PING:
            try:
                sock.sendall(encode(CMD_PONG))
            except OSError:
                pass
            continue

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
                    if receiver_flips >= 2:
                        my_turn = False
                    elif receiver_flips == 1:
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
                time.sleep(3.0)
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

                render_board()
                render_status("Fim de jogo! Revelando todas as cartas...")
                time.sleep(3.0)

                render_board()
                print("=" * 42)
                print("         FIM DE JOGO!")
                print("=" * 42)

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
                if arg == "ALREADY_OPEN" and my_turn:
                    if receiver_flips == 0:
                        print(f"  >> Escolha a PRIMEIRA carta (0-15): ", flush=True)
                    else:
                        print(f"  >> Escolha a SEGUNDA carta (0-15): ", flush=True)

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

    t = threading.Thread(target=receiver, args=(sock,), daemon=True)
    t.start()

    inp = threading.Thread(target=input_listener, daemon=True)
    inp.start()

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
                        with board_lock:
                            if revealed[pos]:
                                print("  Carta ja revelada! Escolha outra posicao.")
                                continue
                        sock.sendall(encode(CMD_FLIP, str(pos)))
                    else:
                        print("  Posicao invalida. Digite entre 0 e 15.")
                except ValueError:
                    print("  Digite um numero de 0 a 15.")
            else:
                time.sleep(0.05)

    except KeyboardInterrupt:
        sock.sendall(encode(CMD_QUIT))
    finally:
        game_over = True
        sock.close()
        print("\n[CLIENTE] Desconectado. Ate a proxima!")


if __name__ == "__main__":
    main()