"""
Cliente do Jogo da Memoria Multiplayer - MGAME/1.0
Possui interface curses com Suporte a Chat Embutido!
Suporta resolução automática de endereços IPv4 e IPv6.
"""
import socket
import threading
import sys
import os
import time

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
    CMD_CHAT, CMD_CHAT_MSG, 
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

try:
    import curses
    HAS_CURSES = True
except ImportError:
    HAS_CURSES = False

status_msg    = ""
status_color  = "info"
_needs_redraw = True

chat_history = [] 
is_typing    = False
chat_buffer  = ""

def set_status(msg, stype="info"):
    global status_msg, status_color, _needs_redraw
    status_msg = msg
    status_color = stype
    _needs_redraw = True

def receiver(sock):
    global my_turn, game_over, my_matches, chat_history, _needs_redraw
    reader = ProtocolReader()
    receiver_flips = 0

    while True:
        raw = reader.recv_message(sock)
        if raw is None:
            if not game_over:
                set_status("Conexao perdida com o servidor. Pressione 'Q' para sair.", "error")
                game_over = True
            break

        command, arg, payload = decode(raw)

        if command == CMD_PING:
            try:
                sock.sendall(encode(CMD_PONG))
            except OSError: pass
            continue
            
        if command == CMD_CHAT_MSG and payload:
            msg_formatada = f"[{payload['player']}]: {payload['msg']}"
            chat_history.append(msg_formatada)
            if len(chat_history) > 3:
                chat_history.pop(0)
            _needs_redraw = True

        elif command == CMD_OK and arg == "WAITING":
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
            set_status(f"{my_name}, SUA VEZ!", "turn")

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
            set_status(f"{player} revelou a posicao {pos} -> [{symbol}]", "info")
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
            time.sleep(1.0)

        elif command == CMD_NO_MATCH and payload:
            positions = payload["positions"]
            player    = payload["player"]
            with board_lock:
                cards_str = " e ".join(f"[{board[p]}]" for p in positions)
            set_status(f"{player} tirou {cards_str}. Sem par!", "error")
            time.sleep(2.5)
            with board_lock:
                for pos in positions:
                    board[pos] = "?"
            set_status("Cartas viradas. Proximo jogador.", "info")

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

if HAS_CURSES:
    cursor_pos = 0

    def _draw_screen(stdscr):
        global cursor_pos, chat_history, is_typing, chat_buffer
        stdscr.erase()
        try:
            stdscr.addstr(1, 4, "=" * 42, curses.color_pair(4))
            stdscr.addstr(2, 4, "   JOGO DA MEMORIA MULTIPLAYER", curses.color_pair(3) | curses.A_BOLD)
            stdscr.addstr(3, 4, "=" * 42, curses.color_pair(4))

            if scores:
                placar_str = " | ".join(f"{n}: {s} pts" for n, s in scores.items())
                stdscr.addstr(5, 4, f"Placar -> {placar_str}", curses.color_pair(1) | curses.A_BOLD)

            revealed_count = sum(1 for r in revealed if r)
            pairs_left = 8 - revealed_count // 2
            stdscr.addstr(6, 4, f"Pares restantes: {pairs_left}", curses.color_pair(3))

            start_y, start_x = 8, 8
            stdscr.addstr(start_y, start_x, "  +-----+-----+-----+-----+", curses.color_pair(4))
            for row in range(4):
                for col in range(4):
                    idx = row * 4 + col
                    with board_lock:
                        is_rev = revealed[idx]
                        sym = board[idx]
                    text = f" {sym} " if (is_rev or sym != "?") else " ? "
                    attrs = curses.color_pair(5)
                    if sym != "?" and sym in "ABCDEFGH":
                        pair_idx = (ord(sym) - ord('A')) % 6 + 1
                        attrs = curses.color_pair(pair_idx) | curses.A_BOLD
                    
                    if idx == cursor_pos and not is_typing:
                        attrs |= curses.A_REVERSE
                        
                    stdscr.addstr(start_y + 1 + row*2, start_x + 2 + col*6, "|", curses.color_pair(4))
                    stdscr.addstr(start_y + 1 + row*2, start_x + 3 + col*6, text, attrs)
                stdscr.addstr(start_y + 1 + row*2, start_x + 2 + 24, "|", curses.color_pair(4))
                stdscr.addstr(start_y + 2 + row*2, start_x, "  +-----+-----+-----+-----+", curses.color_pair(4))

            color_map = {
                "info": curses.color_pair(4), "error": curses.color_pair(2),
                "turn": curses.color_pair(3), "win": curses.color_pair(1),
            }
            c = color_map.get(status_color, curses.color_pair(7))
            stdscr.addstr(18, 4, f">> {status_msg}", c | curses.A_BOLD)
            
            chat_y = 19
            stdscr.addstr(chat_y, 4, "-"*17 + " CHAT " + "-"*17, curses.color_pair(6))
            
            for i, msg in enumerate(chat_history):
                stdscr.addstr(chat_y + 1 + i, 4, msg, curses.color_pair(7))
            
            if is_typing:
                stdscr.addstr(chat_y + 5, 4, f"[Mensagem]: {chat_buffer}_", curses.color_pair(3))
            else:
                stdscr.addstr(chat_y + 5, 4, "[T] Abrir Chat | [Setas] Mover | [ENTER] Virar | [Q] Sair", curses.color_pair(7))
                
        except curses.error:
            pass
        stdscr.refresh()

    def _tui_loop(stdscr, sock):
        global cursor_pos, game_over, is_typing, chat_buffer
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
            _draw_screen(stdscr)
            try:
                ch = stdscr.getch()
            except curses.error:
                ch = -1

            if game_over and ch in [ord('q'), ord('Q')]:
                break
            
            if ch == -1: continue

            if is_typing:
                if ch in (10, 13, curses.KEY_ENTER): 
                    if chat_buffer.strip():
                        try: sock.sendall(encode(CMD_CHAT, chat_buffer.strip()))
                        except: pass
                    is_typing = False
                    chat_buffer = ""
                elif ch == 27: 
                    is_typing = False
                    chat_buffer = ""
                elif ch in (8, 127, curses.KEY_BACKSPACE):
                    chat_buffer = chat_buffer[:-1]
                elif 32 <= ch <= 126: 
                    if len(chat_buffer) < 40: 
                        chat_buffer += chr(ch)
            else:
                if ch in [ord('q'), ord('Q')]:
                    if not game_over:
                        try: sock.sendall(encode(CMD_QUIT))
                        except Exception: pass
                    break
                elif ch in [ord('t'), ord('T')]: 
                    is_typing = True
                    chat_buffer = ""
                elif ch == curses.KEY_UP and cursor_pos >= 4:
                    cursor_pos -= 4
                elif ch == curses.KEY_DOWN and cursor_pos <= 11:
                    cursor_pos += 4
                elif ch == curses.KEY_LEFT and cursor_pos % 4 != 0:
                    cursor_pos -= 1
                elif ch == curses.KEY_RIGHT and cursor_pos % 4 != 3:
                    cursor_pos += 1
                elif ch in (10, 13, 32, curses.KEY_ENTER):
                    if my_turn:
                        with board_lock:
                            is_rev = revealed[cursor_pos]
                        if not is_rev:
                            try:
                                sock.sendall(encode(CMD_FLIP, str(cursor_pos)))
                            except Exception:
                                pass
                        else:
                            set_status("Carta ja revelada! Escolha outra.", "error")
                    else:
                        set_status("Aguarde a sua vez para jogar!", "error")

        sock.close()

else:
    import queue
    input_queue = queue.Queue()

    CORES_CARTAS = {
        "A": "\033[91m", "B": "\033[92m", "C": "\033[93m",
        "D": "\033[94m", "E": "\033[95m", "F": "\033[96m",
        "G": "\033[92;1m", "H": "\033[93;1m",
    }
    R = "\033[0m"; VR = "\033[92m"; VM = "\033[91m"
    AM = "\033[93m"; AZ = "\033[94m"; CI = "\033[96m"; BR = "\033[1m"

    def _clear():
        os.system("cls" if os.name == "nt" else "clear")

    def _console_render():
        _clear()
        print(f"{CI}{'=' * 42}{R}")
        print(f"{AM}   JOGO DA MEMORIA MULTIPLAYER{R}")
        print(f"{CI}{'=' * 42}{R}")
        if scores:
            placar = "  " + f"  {R}".join(f"{BR}{n}{R}: {VR}{s}{R} pts" for n, s in scores.items())
            print(f"{CI}  Placar ->{R}{placar}")
        revealed_count = sum(1 for r in revealed if r)
        print(f"  Pares restantes: {8 - revealed_count // 2}")
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

        msg = status_msg
        if "PAR!" in msg or "Vencedor" in msg or "VENCEDOR" in msg:
            msg = f"{VR}{msg}{R}"
        elif "erro" in msg or "Erro" in msg or "ERRO" in msg or "Sem par" in msg:
            msg = f"{VM}{msg}{R}"
        elif "SUA VEZ" in msg:
            msg = f"{AM}{msg}{R}"
        print(f"  >> {msg}")
        
        if chat_history:
            print(f"  {AZ}--- Chat ---{R}")
            for chat in chat_history:
                print(f"  {chat}")
            print()
            
        if my_turn:
            print(f"  {AM}Digite a posicao (0-15) ou /c <mensagem> para o chat:{R} ", end="", flush=True)
        else:
            print(f"  {AM}Aguarde sua vez, ou digite /c <mensagem> para o chat:{R} ", end="", flush=True)

    def _input_listener():
        while not game_over:
            try:
                line = sys.stdin.readline()
                if line:
                    input_queue.put(line.strip())
            except (EOFError, OSError):
                break

    def _console_main(sock):
        global my_turn, game_over, _needs_redraw
        t = threading.Thread(target=receiver, args=(sock,), daemon=True)
        t.start()
        inp = threading.Thread(target=_input_listener, daemon=True)
        inp.start()

        try:
            while not game_over:
                if _needs_redraw:
                    _console_render()
                    _needs_redraw = False
                    
                try:
                    entry = input_queue.get(timeout=0.1)
                except queue.Empty:
                    continue
                    
                if not entry: continue
                
                if entry.startswith("/c "):
                    sock.sendall(encode(CMD_CHAT, entry[3:]))
                    _needs_redraw = True
                    continue
                    
                if entry.lower() in ("quit", "sair", "q"):
                    sock.sendall(encode(CMD_QUIT))
                    break
                    
                if my_turn:
                    try:
                        pos = int(entry)
                        if 0 <= pos <= 15:
                            with board_lock:
                                if revealed[pos]:
                                    print("\n  Carta ja revelada! Escolha outra posicao.")
                                    _needs_redraw = True
                                    continue
                            sock.sendall(encode(CMD_FLIP, str(pos)))
                            _needs_redraw = True
                        else:
                            print("\n  Posicao invalida. Digite entre 0 e 15.")
                            _needs_redraw = True
                    except ValueError:
                        print("\n  Digite um numero ou /c para chat.")
                        _needs_redraw = True
        except KeyboardInterrupt:
            sock.sendall(encode(CMD_QUIT))
        finally:
            game_over = True
            sock.close()


# =============================================================================
# MENU INTERATIVO DE INICIALIZAÇÃO
# =============================================================================

def interactive_menu(stdscr):
    curses.curs_set(0)
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(1, curses.COLOR_CYAN, -1)

    options = [
        " Local (Jogar neste mesmo computador)",
        " Conectar via IPv4 (Wi-Fi de casa, Ex: 192.168.1.15)",
        " Conectar via IPv6 (Internet, Ex: 2804:14d::1)"
    ]
    current_row = 0

    while True:
        stdscr.clear()
        stdscr.addstr(2, 4, "=== JOGO DA MEMORIA MULTIPLAYER ===", curses.color_pair(1) | curses.A_BOLD)
        stdscr.addstr(4, 4, "Use as SETAS para escolher a rede e aperte ENTER:")

        for idx, row in enumerate(options):
            x = 4
            y = 6 + idx
            if idx == current_row:
                stdscr.addstr(y, x, " > " + row + " ", curses.A_REVERSE)
            else:
                stdscr.addstr(y, x, "   " + row)

        stdscr.refresh()
        key = stdscr.getch()

        if key == curses.KEY_UP and current_row > 0:
            current_row -= 1
        elif key == curses.KEY_DOWN and current_row < len(options) - 1:
            current_row += 1
        elif key in [10, 13, 32, curses.KEY_ENTER]:
            return current_row

def main():
    global my_name, my_turn, game_over
    server_ip = "localhost"

    sys.stdout.write("\x1b[8;35;85t")
    sys.stdout.flush()
    # Se a pessoa só clicou 2 vezes no script (sem parâmetros difíceis no terminal)
    if len(sys.argv) == 1:
        choice = 0
        
        # Abre o menu das setinhas temporariamente
        if HAS_CURSES:
            try:
                choice = curses.wrapper(interactive_menu)
            except Exception:
                choice = 0
        else:
            # Fallback caso a pessoa rode num Windows muito antigo
            print("\n=== JOGO DA MEMORIA MULTIPLAYER ===")
            print("1. Local (Jogar neste mesmo computador)")
            print("2. Conectar via IPv4 (Wi-Fi de casa, Ex: 192.168.1.15)")
            print("3. Conectar via IPv6 (Internet, Ex: 2804:14d::1)")
            resp = input("\nEscolha a forma de conexao (1/2/3): ").strip()
            if resp == "2": choice = 1
            elif resp == "3": choice = 2

        # Limpa o terminal para fazer as perguntas de texto de forma limpa
        os.system("cls" if os.name == "nt" else "clear")
        print("\n=== CONFIGURAÇÃO DO JOGADOR ===\n")

        # Pergunta o apelido
        resp_nome = input("Digite seu apelido: ").strip()
        if resp_nome:
            my_name = resp_nome
        else:
            my_name = "Jogador"

        # Pede o IP apenas se a pessoa NÃO escolheu jogar Localmente
        if choice == 1:
            resp_ip = input("\nDigite o endereco IPv4 do servidor (Ex: 192.168.0.5): ").strip()
            if resp_ip: server_ip = resp_ip
        elif choice == 2:
            resp_ip = input("\nDigite o endereco IPv6 do servidor (Ex: 2804:14d::1): ").strip()
            if resp_ip: server_ip = resp_ip

    else:
        # Modo "Avançado": Se o usuário preencheu no terminal (ex: python client.py Alice 192.168.1.15)
        my_name = sys.argv[1]
        if len(sys.argv) > 2:
            server_ip = sys.argv[2]

    # Conecta ao Servidor com a Escolha Inteligente
    try:
        sock = socket.create_connection((server_ip, PORT))
    except OSError as e:
        print(f"\n[CLIENTE] Nao foi possivel conectar em {server_ip}:{PORT}. Servidor esta rodando?")
        return

    sock.sendall(encode(CMD_JOIN, my_name))

    # Inicia a Interface do Jogo (Tabuleiro e Chat)
    if HAS_CURSES:
        curses.wrapper(_tui_loop, sock)
    else:
        _console_main(sock)

    print(f"\n[CLIENTE] Desconectado. Ate a proxima!")

if __name__ == "__main__":
    main()