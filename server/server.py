"""
Servidor arbitro do Jogo da Memoria Multiplayer - MGAME/1.0
- Aguarda exatamente 2 jogadores
- Controla tabuleiro, turnos, pontuacao e vitoria
- Faz broadcast de eventos para ambos os clientes
- Possui controle de inatividade (Heartbeat)
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
    ARG_WAITING,
    ERR_NAME_TAKEN, ERR_NOT_YOUR_TURN,
    ERR_INVALID_POS, ERR_ALREADY_OPEN,
)

HOST = "0.0.0.0"
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
        self.last_seen = {}  # Armazena o timestamp de cada jogador

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
    # Verificar se as conexões estão ativas
    while True:
        time.sleep(10) # Avalia a cada 10 segundos
        now = time.time()

        stale_connections = []
        with room.lock:
            for p in list(room.players):
                name = p["name"]
                conn = p["conn"]
                last = room.last_seen.get(name, now)

                if now - last > 10:
                    print(f"[SERVER] Timeout! Desconectando '{name}' por inatividade.")
                    stale_connections.append((name, conn))
                else:
                    try:
                        conn.sendall(encode(CMD_PING))
                    except Exception:
                        pass

        # Fecha conexões FORA do lock para evitar deadlock com handle_client
        for name, conn in stale_connections:
            try:
                conn.close()
            except Exception:
                pass


def handle_client(conn, addr):
    player_name = None
    reader = ProtocolReader()

    try:
        # -- JOIN --
        raw = reader.recv_message(conn)
        if raw is None:
            return
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
            
            # Inicializa o heartbeat do jogador
            room.last_seen[player_name] = time.time()
            player_count = len(room.players)

        print(f"[SERVER] '{player_name}' entrou ({player_count}/2)")
        conn.sendall(encode(CMD_OK, ARG_WAITING))

        # -- Aguarda 2o jogador --
        while True:
            with room.lock:
                if len(room.players) == 2 and not room.started:
                    room.started = True
                    start_game = True
                    break
                elif room.started:
                    start_game = False
                    break
            threading.Event().wait(0.2)

        if start_game:
            _start_game()

        # -- Loop principal do jogo --
        while True:
            raw = reader.recv_message(conn)
            if raw is None:
                break
                
            # O cliente respondeu -> Atualiza o tempo na memória
            with room.lock:
                room.last_seen[player_name] = time.time()

            command, arg, _ = decode(raw)

            # Se for só o PONG do heartbeat -> não faz mais nada com esse pacote
            if command == CMD_PONG:
                continue

            if command == CMD_FLIP:
                _handle_flip(player_name, arg, conn)
            elif command == CMD_QUIT:
                conn.sendall(encode(CMD_BYE))
                break
            else:
                conn.sendall(encode(CMD_ERR, "UNKNOWN_COMMAND"))

    except Exception as e:
        print(f"[SERVER] Erro com {addr}: {e}")
    finally:
        if player_name:
            print(f"[SERVER] '{player_name}' desconectou.")
            with room.lock:
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

# Notifica o jogador atual e o outro jogador sobre quem deve jogar
def _notify_turn():
    current = room.players[room.current_turn]
    other = room.other_player(current["name"])
    current["conn"].sendall(encode(CMD_YOUR_TURN))
    if other:
        other["conn"].sendall(encode(CMD_WAIT_TURN, current["name"]))
    print(f"[SERVER] Vez de '{current['name']}'")

# Lógica de FLIP: valida jogada -> atualiza estado -> faz broadcast -> verifica fim de jogo
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

# Fim de jogo: calcula vencedor, envia GAME_OVER e imprime resultado no console
def _end_game():
    scores = {p["name"]: p["score"] for p in room.players}
    s = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    winner = s[0][0] if s[0][1] != s[1][1] else "EMPATE"
    room.broadcast(encode(CMD_GAME_OVER, "", {
        "scores": scores,
        "winner": winner,
    }))
    print(f"[SERVER] Fim de jogo! Vencedor: {winner} | Placar: {scores}")

def main():
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((HOST, PORT))
    srv.listen(2)
    print(f"[SERVER] MGAME/1.0 aguardando jogadores em {HOST}:{PORT}...")

    # Inicia a thread que monitora inatividade
    t_monitor = threading.Thread(target=monitor_heartbeats, daemon=True)
    t_monitor.start()

    while True:
        try:
            conn, addr = srv.accept()
            print(f"[SERVER] Conexao de {addr}")
            t = threading.Thread(target=handle_client, args=(conn, addr), daemon=True)
            t.start()
        except KeyboardInterrupt:
            print("\n[SERVER] Encerrando.")
            break

    srv.close()


if __name__ == "__main__":
    main()