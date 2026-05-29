"""
Servidor arbitro do Jogo da Memoria Multiplayer - MGAME/1.0
- Aguarda exatamente 2 jogadores
- Controla tabuleiro, turnos, pontuacao e vitoria
- Faz broadcast de eventos para ambos os clientes
"""
import socket
import threading
import random
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from shared.protocol import (
    encode, decode, recv_message,
    CMD_JOIN, CMD_FLIP, CMD_QUIT,
    CMD_OK, CMD_ERR, CMD_GAME_START,
    CMD_YOUR_TURN, CMD_WAIT_TURN,
    CMD_CARD_REVEALED, CMD_MATCH, CMD_NO_MATCH,
    CMD_SCORE_UPDATE, CMD_GAME_OVER,
    CMD_PLAYER_LEFT, CMD_BYE,
    ARG_WAITING,
    ERR_NAME_TAKEN, ERR_NOT_YOUR_TURN,
    ERR_INVALID_POS, ERR_ALREADY_OPEN,
)

HOST       = "0.0.0.0"
PORT       = 9000
BOARD_SIZE = 16


class GameRoom:
    """Gerencia o estado completo de uma partida."""

    def __init__(self):
        self.players      = []
        self.board        = []
        self.revealed     = []
        self.current_turn = 0
        self.first_flip   = None
        self.lock         = threading.Lock()
        self.started      = False

    def build_board(self):
        symbols = list("ABCDEFGH") * 2
        random.shuffle(symbols)
        self.board    = symbols
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


def handle_client(conn, addr):
    player_name = None

    try:
        # -- JOIN ----------------------------------------------------------
        raw = recv_message(conn)
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
            player_count = len(room.players)

        print(f"[SERVER] '{player_name}' entrou ({player_count}/2)")
        conn.sendall(encode(CMD_OK, ARG_WAITING))

        # -- Aguarda 2o jogador -------------------------------------------
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

        # -- Loop principal do jogo ---------------------------------------
        while True:
            raw = recv_message(conn)
            if raw is None:
                break
            command, arg, _ = decode(raw)

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
            other = room.other_player(player_name)
            if other:
                try:
                    other["conn"].sendall(encode(CMD_PLAYER_LEFT, player_name))
                except Exception:
                    pass
            with room.lock:
                room.players = [p for p in room.players if p["name"] != player_name]
        conn.close()


def _start_game():
    """Monta o tabuleiro e notifica ambos os jogadores."""
    room.build_board()
    names = [p["name"] for p in room.players]
    payload = {
        "board_size": BOARD_SIZE,
        "players":    names,
        "hidden":     ["?" for _ in room.board],
    }
    room.broadcast(encode(CMD_GAME_START, "", payload))
    print(f"[SERVER] Jogo iniciado! Jogadores: {names}")
    _notify_turn()


def _notify_turn():
    """Avisa de quem e o turno."""
    current = room.players[room.current_turn]
    other   = room.other_player(current["name"])
    current["conn"].sendall(encode(CMD_YOUR_TURN))
    if other:
        other["conn"].sendall(encode(CMD_WAIT_TURN, current["name"]))
    print(f"[SERVER] Vez de '{current['name']}'")


def _handle_flip(player_name: str, arg: str, conn):
    """Processa o comando FLIP de um jogador."""
    with room.lock:
        # Valida turno
        if room.players[room.current_turn]["name"] != player_name:
            conn.sendall(encode(CMD_ERR, ERR_NOT_YOUR_TURN))
            return

        # Valida posicao
        try:
            pos = int(arg)
            assert 0 <= pos < BOARD_SIZE
        except (ValueError, AssertionError):
            conn.sendall(encode(CMD_ERR, ERR_INVALID_POS))
            return

        # Valida se carta ja foi revelada permanentemente
        if room.revealed[pos]:
            conn.sendall(encode(CMD_ERR, ERR_ALREADY_OPEN))
            return

        symbol = room.board[pos]

        # Broadcast: carta revelada
        room.broadcast(encode(CMD_CARD_REVEALED, "", {
            "pos":    pos,
            "symbol": symbol,
            "player": player_name,
        }))

        # Primeira carta do turno
        if room.first_flip is None:
            room.first_flip = (pos, symbol)
            return

        # Segunda carta do turno
        first_pos, first_symbol = room.first_flip
        room.first_flip = None

        if first_symbol == symbol:
            # -- PAR ENCONTRADO -------------------------------------------
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
                _end_game()
                return
        else:
            # -- SEM PAR --------------------------------------------------
            room.broadcast(encode(CMD_NO_MATCH, "", {
                "positions": [first_pos, pos],
                "player":    player_name,
            }))
            # Passa o turno
            room.current_turn = 1 - room.current_turn

    _notify_turn()


def _end_game():
    """Determina vencedor e encerra a partida."""
    scores  = {p["name"]: p["score"] for p in room.players}
    s       = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    winner  = s[0][0] if s[0][1] != s[1][1] else "EMPATE"
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
