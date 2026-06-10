"""
Cliente do Jogo da Memoria Multiplayer - MGAME/1.0
(Versão com Interface Gráfica no Terminal - Curses)
"""
import socket
import threading
import sys
import os
import time
import curses

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from shared.protocol import (
    encode, decode, ProtocolReader,
    CMD_JOIN, CMD_FLIP, CMD_QUIT,
    CMD_OK, CMD_ERR, CMD_GAME_START,
    CMD_YOUR_TURN, CMD_WAIT_TURN,
    CMD_CARD_REVEALED, CMD_MATCH, CMD_NO_MATCH,
    CMD_SCORE_UPDATE, CMD_GAME_OVER,
    CMD_PLAYER_LEFT, CMD_BYE,
    CMD_PING, CMD_PONG,
)

PORT = 9000

board        = ["?"] * 16
revealed     = [False] * 16
scores       = {}
my_turn      = False
game_over    = False
my_name      = ""
my_matches   = []
board_lock   = threading.Lock()

status_msg   = ""
status_color = "info"
cursor_pos   = 0

def set_status(msg, stype="info"):
    global status_msg, status_color
    status_msg = msg
    status_color = stype

def draw_screen(stdscr):
    stdscr.erase()
    try:
        # Título
        stdscr.addstr(1, 4, "=" * 42, curses.color_pair(4))
        stdscr.addstr(2, 4, "   JOGO DA MEMORIA MULTIPLAYER", curses.color_pair(3) | curses.A_BOLD)
        stdscr.addstr(3, 4, "=" * 42, curses.color_pair(4))

        # Placar
        if scores:
            placar_str = " | ".join(f"{n}: {s} pts" for n, s in scores.items())
            stdscr.addstr(5, 4, f"Placar -> {placar_str}", curses.color_pair(1) | curses.A_BOLD)

        # Pares restantes
        revealed_count = sum(1 for r in revealed if r)
        pairs_left = 8 - revealed_count // 2
        stdscr.addstr(6, 4, f"Pares restantes: {pairs_left}", curses.color_pair(3))

        # Tabuleiro 4x4
        start_y = 8
        start_x = 8
        stdscr.addstr(start_y, start_x, "  +-----+-----+-----+-----+", curses.color_pair(4))
        for row in range(4):
            for col in range(4):
                idx = row * 4 + col
                with board_lock:
                    is_rev = revealed[idx]
                    sym = board[idx]
                
                if is_rev or sym != "?":
                    text = f" {sym} "
                else:
                    text = " ? "
                
                # Definir cor da carta
                attrs = curses.color_pair(5)
                if sym != "?" and sym in "ABCDEFGH":
                    pair_idx = (ord(sym) - ord('A')) % 6 + 1
                    attrs = curses.color_pair(pair_idx) | curses.A_BOLD
                    
                # Efeito visual de seleção (cursor)
                if idx == cursor_pos:
                    attrs |= curses.A_REVERSE
                
                stdscr.addstr(start_y + 1 + row*2, start_x + 2 + col*6, "|", curses.color_pair(4))
                stdscr.addstr(start_y + 1 + row*2, start_x + 3 + col*6, text, attrs)
            
            stdscr.addstr(start_y + 1 + row*2, start_x + 2 + 24, "|", curses.color_pair(4))
            stdscr.addstr(start_y + 2 + row*2, start_x, "  +-----+-----+-----+-----+", curses.color_pair(4))

        # Mensagem de Status (Avisos de rede, turnos, etc)
        color_map = {
            "info": curses.color_pair(4),
            "error": curses.color_pair(2),
            "turn": curses.color_pair(3),
            "win": curses.color_pair(1)
        }
        c = color_map.get(status_color, curses.color_pair(7))
        stdscr.addstr(18, 4, f">> {status_msg}", c | curses.A_BOLD)
        
        # Instruções fixas
        stdscr.addstr(20, 4, "Controles: [Setas] mover | [ENTER/ESPACO] virar carta | [Q] sair", curses.color_pair(7))

    except curses.error:
        pass
        
    stdscr.refresh()

def receiver(sock):
    global my_turn, game_over, my_matches
    reader = ProtocolReader()
    receiver_flips = 0

    while True:
        raw = reader.recv_message(sock)
        if raw is None:
            if not game_over:
                set_status("Conexão perdida com o servidor. Pressione 'Q' para sair.", "error")
                game_over = True
            break

        command, arg, payload = decode(raw)

        if command == CMD_PING:
            try:
                sock.sendall(encode(CMD_PONG))
            except OSError:
                pass
            continue

        # A partir daqui, só usamos o "with board_lock" nas linhas EXATAS 
        # que modificam o tabuleiro, deixando os time.sleep() livres!
        
        if command == CMD_OK and arg == "WAITING":
            set_status("Conectado! Aguardando segundo jogador...", "info")

        elif command == CMD_GAME_START and payload:
            board_size = payload.get("board_size", 16)
            with board_lock:
                for i in range(board_size):
                    board[i]    = "?"
                    revealed[i] = False
                my_matches.clear()
            players = payload.get("players", [])
            set_status(f"Jogo iniciado! {' vs '.join(players)}", "info")
            receiver_flips = 0

        elif command == CMD_YOUR_TURN:
            my_turn = True
            receiver_flips = 0
            set_status(f"{my_name}, SUA VEZ! Mova com as setas e aperte ENTER.", "turn")

        elif command == CMD_WAIT_TURN:
            my_turn = False
            receiver_flips = 0
            set_status(f"Vez de {arg}... aguarde.", "info")

        elif command == CMD_CARD_REVEALED and payload:
            pos    = payload["pos"]
            symbol = payload["symbol"]
            player = payload["player"]
            with board_lock:
                board[pos] = symbol
            set_status(f"{player} revelou a posição {pos} -> [{symbol}]", "info")
            if player == my_name:
                receiver_flips += 1
                if receiver_flips >= 2:
                    my_turn = False
                elif receiver_flips == 1:
                    set_status("Agora escolha a SEGUNDA carta.", "turn")

        elif command == CMD_MATCH and payload:
            positions = payload["positions"]
            symbol    = payload["symbol"]
            player    = payload["player"]
            with board_lock:
                for pos in positions:
                    revealed[pos] = True
                    board[pos]    = symbol
            set_status(f"PAR! {player} encontrou [{symbol}]!", "win")
            if player == my_name:
                my_matches.append((symbol, list(positions)))
            time.sleep(1.0) # Fora do lock: a tela pisca verde e você vê o par!

        elif command == CMD_NO_MATCH and payload:
            positions = payload["positions"]
            player    = payload["player"]
            
            with board_lock:
                cards_str = " e ".join(f"[{board[p]}]" for p in positions)
                
            set_status(f"{player} tirou {cards_str}. Sem par!", "error")
            
            time.sleep(2.5) # O SEGREDOS ESTÁ AQUI: Dorme com o lock destrancado, permitindo a tela desenhar!
            
            with board_lock:
                for pos in positions:
                    board[pos] = "?"
            set_status(f"Cartas viradas. Próximo jogador.", "info")

        elif command == CMD_SCORE_UPDATE and payload:
            scores.update(payload.get("scores", {}))

        elif command == CMD_GAME_OVER and payload:
            my_turn   = False
            final_scores = payload.get("scores", {})
            winner       = payload.get("winner", "?")
            scores.update(final_scores)

            set_status("Fim de jogo! Revelando todas as cartas...", "info")
            time.sleep(2.0)

            if winner == "EMPATE":
                msg = "FIM DE JOGO: EMPATE! | "
            else:
                msg = f"VENCEDOR: {winner}! | "
            
            msg += " ".join(f"{n}: {s} pts" for n,s in final_scores.items())
            msg += " | Pressione 'Q' para sair."

            set_status(msg, "win")
            game_over = True

        elif command == CMD_PLAYER_LEFT:
            my_turn   = False
            set_status(f"{arg} abandonou a partida. Pressione 'Q' para sair.", "error")
            game_over = True

        elif command == CMD_ERR:
            set_status(f"ERRO: {arg}", "error")

        elif command == CMD_BYE:
            game_over = True
            break

def tui_loop(stdscr, sock):
    global cursor_pos, game_over

    curses.curs_set(0)
    stdscr.timeout(100) 
    
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(1, curses.COLOR_GREEN, -1)
    curses.init_pair(2, curses.COLOR_RED, -1)
    curses.init_pair(3, curses.COLOR_YELLOW, -1)
    curses.init_pair(4, curses.COLOR_CYAN, -1)
    curses.init_pair(5, curses.COLOR_MAGENTA, -1)
    curses.init_pair(6, curses.COLOR_BLUE, -1)
    curses.init_pair(7, curses.COLOR_WHITE, -1)

    t = threading.Thread(target=receiver, args=(sock,), daemon=True)
    t.start()

    while True:
        draw_screen(stdscr)

        try:
            ch = stdscr.getch()
        except curses.error:
            ch = -1

        if ch in [ord('q'), ord('Q')]:
            if not game_over:
                try:
                    sock.sendall(encode(CMD_QUIT))
                except: pass
            break

        if game_over:
            continue

        if ch == curses.KEY_UP:
            if cursor_pos >= 4: cursor_pos -= 4
        elif ch == curses.KEY_DOWN:
            if cursor_pos <= 11: cursor_pos += 4
        elif ch == curses.KEY_LEFT:
            if cursor_pos % 4 != 0: cursor_pos -= 1
        elif ch == curses.KEY_RIGHT:
            if cursor_pos % 4 != 3: cursor_pos += 1
        elif ch in [10, 13, 32, curses.KEY_ENTER]: 
            if my_turn:
                with board_lock:
                    is_rev = revealed[cursor_pos]
                if not is_rev:
                    try:
                        sock.sendall(encode(CMD_FLIP, str(cursor_pos)))
                    except Exception:
                        pass
                else:
                    set_status("Carta já revelada! Escolha outra.", "error")
            else:
                set_status("Aguarde a sua vez para jogar!", "error")

    sock.close()

def main():
    global my_name
    server_ip = "127.0.0.1" 

    if len(sys.argv) > 1:
        my_name = sys.argv[1]
    else:
        my_name = input("Digite seu apelido: ").strip()
        if not my_name:
            my_name = "Jogador"

    if len(sys.argv) > 2:
        server_ip = sys.argv[2]

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.connect((server_ip, PORT))
    except ConnectionRefusedError:
        print(f"[CLIENTE] Nao foi possivel conectar em {server_ip}:{PORT}. Servidor esta rodando?")
        return

    sock.sendall(encode(CMD_JOIN, my_name))
    curses.wrapper(tui_loop, sock)
    print("\n[CLIENTE] Desconectado. Até a próxima!")

if __name__ == "__main__":
    main()