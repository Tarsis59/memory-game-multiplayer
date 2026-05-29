"""
Protocolo MGAME/1.0 — Memory Game Multiplayer
Formato: COMANDO ARGUMENTO\r\n[JSON\r\n]
"""
import json

ENCODING  = "utf-8"
DELIMITER = "\r\n"

# Cliente -> Servidor
CMD_JOIN = "JOIN"
CMD_FLIP = "FLIP"
CMD_QUIT = "QUIT"

# Servidor -> Cliente
CMD_OK             = "OK"
CMD_ERR            = "ERR"
CMD_GAME_START     = "GAME_START"
CMD_YOUR_TURN      = "YOUR_TURN"
CMD_WAIT_TURN      = "WAIT_TURN"
CMD_CARD_REVEALED  = "CARD_REVEALED"
CMD_MATCH          = "MATCH"
CMD_NO_MATCH       = "NO_MATCH"
CMD_SCORE_UPDATE   = "SCORE_UPDATE"
CMD_GAME_OVER      = "GAME_OVER"
CMD_PLAYER_LEFT    = "PLAYER_LEFT"
CMD_BYE            = "BYE"

# Args de OK
ARG_WAITING    = "WAITING"
ARG_REGISTERED = "REGISTERED"

# Args de ERR
ERR_NAME_TAKEN    = "NAME_TAKEN"
ERR_NOT_YOUR_TURN = "NOT_YOUR_TURN"
ERR_INVALID_POS   = "INVALID_POS"
ERR_ALREADY_OPEN  = "ALREADY_OPEN"


def encode(command: str, arg: str = "", payload: dict = None) -> bytes:
    line = command
    if arg:
        line += f" {arg}"
    line += DELIMITER
    if payload is not None:
        line += json.dumps(payload, ensure_ascii=False) + DELIMITER
    return line.encode(ENCODING)


def decode(raw: str):
    """Retorna (command, arg, payload|None)."""
    parts  = raw.strip().split(DELIMITER, 1)
    header = parts[0].strip()
    body   = parts[1].strip() if len(parts) > 1 and parts[1].strip() else None

    tokens  = header.split(" ", 1)
    command = tokens[0]
    arg     = tokens[1] if len(tokens) > 1 else ""

    payload = None
    if body:
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            payload = None

    return command, arg, payload


def recv_message(sock):
    """Le do socket ate receber mensagem completa. Retorna str ou None."""
    buffer = ""
    while True:
        try:
            chunk = sock.recv(4096).decode(ENCODING)
            if not chunk:
                return None
            buffer += chunk
            if buffer.count(DELIMITER) >= 2:
                return buffer
            if buffer.endswith(DELIMITER):
                return buffer
        except Exception:
            return None
