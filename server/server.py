"""
Servidor arbitro do Jogo da Memoria Multiplayer - MGAME/1.0
- Aguarda exatamente 2 jogadores
- Controla tabuleiro, turnos, pontuacao e vitoria
- Faz broadcast de eventos e CHAT para ambos os clientes
- Possui controle de inatividade (Heartbeat)
- Suporta conexões IPv4 e IPv6 simultaneamente (Dual-Stack)
"""
import socket
import threading
import random
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
    ARG_WAITING,
    ERR_NAME_TAKEN, ERR_NOT_YOUR_TURN,
    ERR_INVALID_POS, ERR_ALREADY_OPEN,
)

HOST = "" # String vazia permite bind em todas as interfaces IPv4 e IPv6
PORT = 9000
BOARD_SIZE = 16

class GameRoom:
    """Gerencia o estado completo de uma partida."""
    def __init__(self):
        self.players = []
        self.board = []
        self.revealed = []
        self.current_turn = 0
        self.first_flip = None
        self.lock = threading.Lock()
        self.started = False
        self.last_seen = {}

    def build_board(self):
        symbols = list("ABCDEFGH") * 2
        random.shuffle(symbols)
        self.board = symbols
        self.revealed = [False] * BOARD_SIZE

    def all_revealed(self):
        return all(self.revealed)

    def broadcast(self, data: bytes):
        for p in self.players:
            try:
                p["conn"].sendall(data)
            except Exception:
                pass

    def other_player(self, name: str):
        for p in self.players:
            if p["name"] != name:
                return p
        return None

room = GameRoom()

def monitor_heartbeats():
    while True:
        time.sleep(10)
        now = time.time()
        stale_connections = []
        with room.lock:
            if not room.started:
                continue
            for p in list(room.players):
                name = p["name"]
                conn = p["conn"]
                last = room.last_seen.get(name, now)
                if now - last > 60: 
                    print(f"[SERVER] Timeout! Desconectando '{name}' por inatividade.")
                    stale_connections.append(p)
                else:
                    try:
                        conn.sendall(encode(CMD_PING))
                    except Exception:
                        pass

        for p in stale_connections:
            try:
                p["conn"].close()
            except Exception:
                pass
            with room.lock:
                if p in room.players:
                    room.players.remove(p)
                    room.last_seen.pop(p["name"], None)

def handle_client(conn, addr):
    player_name = None
    reader = ProtocolReader()

    try:
        raw = reader.recv_message(conn)
        if raw is None: return
        command, arg, _ = decode(raw)

        if command != CMD_JOIN or not arg.strip():
            conn.sendall(encode(CMD_ERR, "EXPECTED_JOIN"))
            return

        player_name = arg.strip()

        with room.lock:
            if len(room.players) >= 2:
                conn.sendall(encode(CMD_ERR, "ROOM_FULL"))
                return
            for p in room.players:
                if p["name"] == player_name:
                    conn.sendall(encode(CMD_ERR, ERR_NAME_TAKEN))
                    return
            room.players.append({"name": player_name, "conn": conn, "score": 0})
            room.last_seen[player_name] = time.time()
            player_count = len(room.players)

        # addr no IPv6 vem como (ip, porta, flowinfo, scopeid)
        # pegamos apenas os dois primeiros para formatar bonito no log
        ip_formatado = f"[{addr[0]}]:{addr[1]}" if len(addr) > 2 else f"{addr[0]}:{addr[1]}"
        print(f"[SERVER] '{player_name}' entrou via {ip_formatado} ({player_count}/2)")
        conn.sendall(encode(CMD_OK, ARG_WAITING))

        conn.settimeout(0.5)
        pre_game = []
        while True:
            with room.lock:
                if len(room.players) == 2 and not room.started:
                    room.started = True
                    start_game = True
                    break
                elif room.started:
                    start_game = False
                    break
            try:
                raw = reader.recv_message(conn)
                if raw is None: return
                cmd, _, _ = decode(raw)
                if cmd == CMD_PONG:
                    with room.lock:
                        room.last_seen[player_name] = time.time()
                else:
                    pre_game.append(raw)
            except socket.timeout:
                continue
        conn.settimeout(None)
        if pre_game:
            reader._buffer = "".join(pre_game) + reader._buffer

        if start_game:
            _start_game()

        while True:
            raw = reader.recv_message(conn)
            if raw is None: break
                
            with room.lock:
                room.last_seen[player_name] = time.time()

            command, arg, _ = decode(raw)

            if command == CMD_PONG:
                continue
            
            elif command == CMD_CHAT:
                msg_text = arg.strip()
                if msg_text:
                    room.broadcast(encode(CMD_CHAT_MSG, "", {
                        "player": player_name,
                        "msg": msg_text
                    }))

            elif command == CMD_FLIP:
                _handle_flip(player_name, arg, conn)
            elif command == CMD_QUIT:
                conn.sendall(encode(CMD_BYE))
                break
            else:
                conn.sendall(encode(CMD_ERR, "UNKNOWN_COMMAND"))

    except Exception as e:
        print(f"[SERVER] Erro com '{player_name}': {e}")
    finally:
        if player_name:
            print(f"[SERVER] '{player_name}' desconectou.")
            with room.lock:
                # ó declara vitória por abandono se o jogo AINDA NÃO TINHA ACABADO
                if not room.all_revealed(): 
                    remaining = room.other_player(player_name)
                    if remaining:
                        scores = {p["name"]: p["score"] for p in room.players if p["name"] != player_name}
                        winner = remaining["name"]
                        try:
                            remaining["conn"].sendall(encode(CMD_GAME_OVER, "", {
                                "scores": scores, "winner": winner
                            }))
                        except Exception:
                            pass
                
                room.players = []
                room.last_seen.pop(player_name, None)
        conn.close()

def _start_game():
    room.build_board()
    names = [p["name"] for p in room.players]
    payload = {
        "board_size": BOARD_SIZE,
        "players": names,
        "hidden": ["?" for _ in room.board],
    }
    room.broadcast(encode(CMD_GAME_START, "", payload))
    print(f"[SERVER] Jogo iniciado! Jogadores: {names}")
    _notify_turn()

def _notify_turn():
    current = room.players[room.current_turn]
    other = room.other_player(current["name"])
    try:
        current["conn"].sendall(encode(CMD_YOUR_TURN))
    except Exception:
        if other:
            other["conn"].sendall(encode(CMD_YOUR_TURN))
            room.current_turn = 1 - room.current_turn
        return
    if other:
        try:
            other["conn"].sendall(encode(CMD_WAIT_TURN, current["name"]))
        except Exception:
            pass
    print(f"[SERVER] Vez de '{current['name']}'")

def _handle_flip(player_name: str, arg: str, conn):
    game_ended = False
    with room.lock:
        if len(room.players) < 2 or room.current_turn >= len(room.players):
            conn.sendall(encode(CMD_ERR, "GAME_OVER"))
            return
        if room.players[room.current_turn]["name"] != player_name:
            conn.sendall(encode(CMD_ERR, ERR_NOT_YOUR_TURN))
            return

        try:
            pos = int(arg)
            assert 0 <= pos < BOARD_SIZE
        except (ValueError, AssertionError):
            conn.sendall(encode(CMD_ERR, ERR_INVALID_POS))
            return

        if room.revealed[pos]:
            conn.sendall(encode(CMD_ERR, ERR_ALREADY_OPEN))
            return

        symbol = room.board[pos]

        room.broadcast(encode(CMD_CARD_REVEALED, "", {
            "pos": pos,
            "symbol": symbol,
            "player": player_name,
        }))

        if room.first_flip is None:
            room.first_flip = (pos, symbol)
            return

        first_pos, first_symbol = room.first_flip
        room.first_flip = None

        if first_symbol == symbol:
            room.revealed[first_pos] = True
            room.revealed[pos]       = True

            for p in room.players:
                if p["name"] == player_name:
                    p["score"] += 1

            scores = {p["name"]: p["score"] for p in room.players}
            room.broadcast(encode(CMD_MATCH, "", {
                "positions": [first_pos, pos],
                "symbol":    symbol,
                "player":    player_name,
            }))
            room.broadcast(encode(CMD_SCORE_UPDATE, "", {"scores": scores}))

            if room.all_revealed():
                game_ended = True
        else:
            room.broadcast(encode(CMD_NO_MATCH, "", {
                "positions": [first_pos, pos],
                "player":    player_name,
            }))
            room.current_turn = 1 - room.current_turn

    if game_ended:
        _end_game()
        return
    _notify_turn()

def _end_game():
    scores = {p["name"]: p["score"] for p in room.players}
    s = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    winner = s[0][0] if s[0][1] != s[1][1] else "EMPATE"
    room.broadcast(encode(CMD_GAME_OVER, "", {
        "scores": scores,
        "winner": winner,
    }))
    print(f"[SERVER] Fim de jogo! Vencedor: {winner} | Placar: {scores}")

# Adicione esta pequena função debaixo do def _end_game(): e antes do def main():
def get_local_ip():
    """Descobre o IP local (IPv4) da máquina de forma dinâmica criando um socket UDP invisível."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Não precisa de ter internet, ele apenas simula uma ligação para ler a interface de rede ativa
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

def main():
    if hasattr(socket, 'has_dualstack_ipv6') and socket.has_dualstack_ipv6():
        srv = socket.create_server((HOST, PORT), family=socket.AF_INET6, dualstack_ipv6=True)
        modo = "Dual-Stack (IPv4 e IPv6)"
    else:
        srv = socket.create_server((HOST, PORT))
        modo = "Apenas IPv4"
        
    srv.listen(2)
    
    # --- NOVO: Mostra o IP de forma amigável ---
    meu_ip = get_local_ip()
    print("="*50)
    print(" SERVIDOR DO JOGO DA MEMORIA INICIADO!")
    print(f" Modo: {modo}")
    print(f" Porta: {PORT}")
    print(f" -> Para jogar neste PC, o cliente liga em: localhost")
    print(f" -> Para jogar na mesma rede, o cliente liga em: {meu_ip}")
    print("="*50)
    print(f"[SERVER] A aguardar por 2 jogadores...")

    t_monitor = threading.Thread(target=monitor_heartbeats, daemon=True)
    t_monitor.start()

    while True:
        try:
            conn, addr = srv.accept()
            t = threading.Thread(target=handle_client, args=(conn, addr), daemon=True)
            t.start()
        except KeyboardInterrupt:
            print("\n[SERVER] A encerrar.")
            break

    srv.close()

if __name__ == "__main__":
    main()