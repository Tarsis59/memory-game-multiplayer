"""
Cliente do Jogo da Memoria Multiplayer - TCP
(Versão Híbrida: Menu em Curses + Interface Gráfica Pygame)
"""
import socket
import threading
import sys
import os
import time

try:
    import pygame
except ImportError:
    print("\n[ERRO] A biblioteca 'pygame' não está instalada.")
    print("Por favor, execute no terminal: pip install pygame")
    sys.exit(1)

try:
    import curses
    HAS_CURSES = True
except ImportError:
    HAS_CURSES = False

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

status_msg    = ""
status_color  = "info"

chat_history = [] 
is_typing    = False
chat_buffer  = ""


def set_status(msg, stype="info"):
    global status_msg, status_color
    status_msg = msg
    status_color = stype


def receiver(sock):
    """Thread em background que processa todos os pacotes TCP da rede."""
    global my_turn, game_over, my_matches, chat_history
    reader = ProtocolReader()
    receiver_flips = 0

    while True:
        raw = reader.recv_message(sock)
        if raw is None:
            if not game_over:
                set_status("Conexão perdida com o servidor.", "error")
                game_over = True
            break

        command, arg, payload = decode(raw)

        if command == CMD_PING:
            try: sock.sendall(encode(CMD_PONG))
            except OSError: pass
            continue
            
        if command == CMD_CHAT_MSG and payload:
            msg_formatada = f"{payload['player']}: {payload['msg']}"
            chat_history.append(msg_formatada)
            if len(chat_history) > 6:
                chat_history.pop(0)

        elif command == CMD_OK and arg == "WAITING":
            set_status("Aguardar pelo 2º jogador...", "info")

        elif command == CMD_GAME_START and payload:
            board_size = payload.get("board_size", 16)
            with board_lock:
                for i in range(board_size):
                    board[i]    = "?"
                    revealed[i] = False
                    my_matches.clear()
            players = payload.get("players", [])
            set_status(f"Jogo Iniciado! {' vs '.join(players)}", "info")
            receiver_flips = 0

        elif command == CMD_YOUR_TURN:
            my_turn = True
            receiver_flips = 0
            set_status(f"{my_name}, É A SUA VEZ!", "turn")

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
            set_status(f"{player} virou a carta {pos}", "info")
            if player == my_name:
                receiver_flips += 1
                if receiver_flips >= 2:
                    my_turn = False
                elif receiver_flips == 1:
                    set_status("Escolha a SEGUNDA carta.", "turn")

        elif command == CMD_MATCH and payload:
            positions = payload["positions"]
            symbol = payload["symbol"]
            player = payload["player"]
            with board_lock:
                for pos in positions:
                    revealed[pos] = True
                    board[pos]    = symbol
            set_status(f"PAR! {player} acertou no [{symbol}]!", "win")
            if player == my_name:
                my_matches.append((symbol, list(positions)))
            time.sleep(1.0)

        elif command == CMD_NO_MATCH and payload:
            positions = payload["positions"]
            player    = payload["player"]
            set_status(f"{player} falhou o par!", "error")
            
            time.sleep(2.5) 
            
            with board_lock:
                for pos in positions:
                    board[pos] = "?"
            set_status("Cartas ocultadas. Próximo jogador.", "info")

        elif command == CMD_SCORE_UPDATE and payload:
            scores.update(payload.get("scores", {}))

        elif command == CMD_GAME_OVER and payload:
            my_turn = False
            final_scores = payload.get("scores", {})
            winner = payload.get("winner", "?")
            scores.update(final_scores)
            
            time.sleep(1.0)
            if winner == "EMPATE":
                set_status("FIM DE JOGO: EMPATE!", "win")
            else:
                set_status(f"VENCEDOR: {winner}!", "win")
            game_over = True

        elif command == CMD_PLAYER_LEFT:
            my_turn = False
            set_status(f"O jogador {arg} abandonou a partida.", "error")
            game_over = True

        elif command == CMD_ERR:
            set_status(f"ERRO: {arg}", "error")

        elif command == CMD_BYE:
            game_over = True
            break


# =============================================================================
# INTERFACE GRÁFICA (PYGAME) E MOTOR DE RENDERIZAÇÃO
# =============================================================================
def start_gui(sock):
    global my_turn, game_over, is_typing, chat_buffer

    pygame.init()
    WIDTH, HEIGHT = 1000, 650
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption(f"Memory Game - Ligado como: {my_name}")
    clock = pygame.time.Clock()

    font_title = pygame.font.SysFont("segoeui", 36, bold=True)
    font_text = pygame.font.SysFont("segoeui", 24)
    font_small = pygame.font.SysFont("segoeui", 18)
    font_card = pygame.font.SysFont("segoeui", 60, bold=True)

    BG_COLOR = (30, 30, 42)
    PANEL_COLOR = (40, 42, 54)
    CARD_BACK = (98, 114, 164)
    CARD_HOVER = (139, 155, 201)
    CARD_REVEALED = (248, 248, 242)
    TEXT_LIGHT = (248, 248, 242)
    LINE_COLOR = (68, 71, 90)

    SYMBOL_COLORS = {
        "A": (255, 85, 85),   "B": (80, 250, 123),
        "C": (241, 250, 140), "D": (139, 233, 253),
        "E": (189, 147, 249), "F": (255, 184, 108),
        "G": (255, 121, 198), "H": (139, 195, 74),
    }

    color_map = {
        "info": (139, 233, 253), "error": (255, 85, 85),
        "turn": (241, 250, 140), "win": (80, 250, 123)
    }

    t = threading.Thread(target=receiver, args=(sock,), daemon=True)
    t.start()

    running = True
    while running:
        mouse_pos = pygame.mouse.get_pos()
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if event.pos[0] > 620 and event.pos[1] > 550:
                    is_typing = True
                else:
                    is_typing = False
                    if my_turn and not game_over:
                        for row in range(4):
                            for col in range(4):
                                idx = row * 4 + col
                                cx = 50 + col * 130
                                cy = 50 + row * 140
                                card_rect = pygame.Rect(cx, cy, 110, 120)
                                if card_rect.collidepoint(event.pos):
                                    with board_lock:
                                        if not revealed[idx] and board[idx] == "?":
                                            try: sock.sendall(encode(CMD_FLIP, str(idx)))
                                            except: pass
                                        else:
                                            set_status("Carta já revelada!", "error")
                    elif not my_turn and not game_over:
                        set_status("Aguarde a sua vez!", "error")

            elif event.type == pygame.KEYDOWN:
                if game_over:
                    if event.key == pygame.K_q or event.key == pygame.K_ESCAPE:
                        running = False
                else:
                    if is_typing:
                        if event.key == pygame.K_RETURN:
                            if chat_buffer.strip():
                                try: sock.sendall(encode(CMD_CHAT, chat_buffer.strip()))
                                except: pass
                            chat_buffer = ""
                            is_typing = False
                        elif event.key == pygame.K_ESCAPE:
                            is_typing = False
                            chat_buffer = ""
                        elif event.key == pygame.K_BACKSPACE:
                            chat_buffer = chat_buffer[:-1]
                        else:
                            if len(chat_buffer) < 30 and event.unicode.isprintable():
                                chat_buffer += event.unicode
                    else:
                        if event.key == pygame.K_t:
                            is_typing = True
                            chat_buffer = ""
                        elif event.key == pygame.K_q:
                            running = False

        screen.fill(BG_COLOR)

        with board_lock:
            for row in range(4):
                for col in range(4):
                    idx = row * 4 + col
                    cx = 50 + col * 130
                    cy = 50 + row * 140
                    card_rect = pygame.Rect(cx, cy, 110, 120)
                    
                    is_rev = revealed[idx]
                    sym = board[idx]

                    if is_rev or sym != "?":
                        pygame.draw.rect(screen, CARD_REVEALED, card_rect, border_radius=12)
                        pygame.draw.rect(screen, LINE_COLOR, card_rect, width=3, border_radius=12)
                        sym_color = SYMBOL_COLORS.get(sym, (0, 0, 0))
                        txt_surface = font_card.render(sym, True, sym_color)
                        txt_rect = txt_surface.get_rect(center=card_rect.center)
                        screen.blit(txt_surface, txt_rect)
                    else:
                        color = CARD_HOVER if card_rect.collidepoint(mouse_pos) and my_turn else CARD_BACK
                        pygame.draw.rect(screen, color, card_rect, border_radius=12)
                        pygame.draw.rect(screen, LINE_COLOR, card_rect, width=3, border_radius=12)
                        pygame.draw.circle(screen, BG_COLOR, card_rect.center, 25, 4)

        panel_rect = pygame.Rect(600, 0, 400, HEIGHT)
        pygame.draw.rect(screen, PANEL_COLOR, panel_rect)
        pygame.draw.line(screen, LINE_COLOR, (600, 0), (600, HEIGHT), 4)

        title_surf = font_title.render("Placar", True, TEXT_LIGHT)
        screen.blit(title_surf, (620, 20))

        y_score = 70
        for p_name, s in scores.items():
            color = (80, 250, 123) if p_name == my_name else TEXT_LIGHT
            sc_surf = font_text.render(f"{p_name}: {s} pontos", True, color)
            screen.blit(sc_surf, (620, y_score))
            y_score += 35

        rev_count = sum(1 for r in revealed if r)
        p_left = 8 - (rev_count // 2)
        stat_surf = font_small.render(f"Pares restantes: {p_left}", True, (241, 250, 140))
        screen.blit(stat_surf, (620, y_score + 10))

        pygame.draw.line(screen, LINE_COLOR, (620, y_score + 40), (980, y_score + 40), 2)

        st_color = color_map.get(status_color, TEXT_LIGHT)
        status_surf = font_text.render(status_msg, True, st_color)
        screen.blit(status_surf, (620, y_score + 60))

        pygame.draw.line(screen, LINE_COLOR, (620, y_score + 110), (980, y_score + 110), 2)

        screen.blit(font_small.render("Chat em direto:", True, (98, 114, 164)), (620, y_score + 120))
        chat_y = y_score + 150
        for msg in chat_history:
            chat_surf = font_small.render(msg, True, TEXT_LIGHT)
            screen.blit(chat_surf, (620, chat_y))
            chat_y += 25

        input_box = pygame.Rect(620, HEIGHT - 80, 360, 40)
        box_color = (255, 121, 198) if is_typing else LINE_COLOR
        pygame.draw.rect(screen, (30, 30, 42), input_box, border_radius=8)
        pygame.draw.rect(screen, box_color, input_box, width=2, border_radius=8)

        if is_typing:
            in_surf = font_small.render(chat_buffer + "|", True, TEXT_LIGHT)
        else:
            in_surf = font_small.render("Clique aqui ou pressione 'T' para o chat", True, (98, 114, 164))
        
        screen.blit(in_surf, (630, HEIGHT - 70))

        pygame.display.flip()
        clock.tick(60)

    try: sock.sendall(encode(CMD_QUIT))
    except: pass
    sock.close()
    pygame.quit()


# =============================================================================
# WIZARD DE TERMINAL E INICIALIZAÇÃO
# =============================================================================

def interactive_menu(stdscr):
    """Menu bonito renderizado com curses."""
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
        stdscr.addstr(2, 4, "=== JOGO DA MEMÓRIA MULTIPLAYER (Pygame Edition) ===", curses.color_pair(1) | curses.A_BOLD)
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
    global my_name
    server_ip = "localhost"

    # Inicia sem argumentos de terminal
    if len(sys.argv) == 1:
        choice = 0
        
        if HAS_CURSES:
            try:
                # Dispara o menu bonitão interativo
                choice = curses.wrapper(interactive_menu)
            except Exception:
                choice = 0
        else:
            # Fallback feio caso não tenha curses (Windows sem o pacote)
            os.system("cls" if os.name == "nt" else "clear")
            print("="*50)
            print("=== JOGO DA MEMÓRIA MULTIPLAYER (Pygame Edition) ===")
            print("="*50)
            print("Selecione onde está o servidor:")
            print("  [1] Jogar localmente (Neste computador)")
            print("  [2] Rede Wi-Fi (IPv4) - Inserir o IP")
            print("  [3] Internet (IPv6) - Inserir o IP")
            
            while True:
                resp = input("\nEscolha (1/2/3): ").strip()
                if resp == '1':
                    choice = 0
                    break
                elif resp == '2':
                    choice = 1
                    break
                elif resp == '3':
                    choice = 2
                    break
                print("Opção inválida.")

        os.system("cls" if os.name == "nt" else "clear")
        print("\n=== CONFIGURAÇÃO DO JOGADOR ===\n")
        my_name = input("Digite o seu apelido: ").strip() or "Jogador"

        if choice == 1:
            server_ip = input("\nDigite o IPv4 do servidor (Ex: 192.168.1.15): ").strip()
        elif choice == 2:
            server_ip = input("\nDigite o IPv6 do servidor (Ex: 2804:14d::1): ").strip()

    else:
        # Pula as perguntas se abrir via terminal
        my_name = sys.argv[1]
        if len(sys.argv) > 2:
            server_ip = sys.argv[2]

    print(f"\nA ligar a {server_ip}:{PORT}...")

    try:
        sock = socket.create_connection((server_ip, PORT), timeout=5)
        sock.settimeout(None) 
    except OSError as e:
        print(f"\n[ERRO] Não foi possível ligar a {server_ip}:{PORT}.")
        print("O servidor está a correr? O IP está correto?")
        return

    sock.sendall(encode(CMD_JOIN, my_name))
    
    # Inicia a Interface Gráfica após concluir as perguntas do terminal
    start_gui(sock)


if __name__ == "__main__":
    main()