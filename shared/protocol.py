"""
Protocolo MGAME/1.0 — Memory Game Multiplayer
Formato: COMANDO ARGUMENTO\r\n[JSON\r\n]
"""
import json
import socket

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


COMMANDS_WITH_PAYLOAD = {
    CMD_GAME_START, CMD_CARD_REVEALED, CMD_MATCH,
    CMD_NO_MATCH, CMD_SCORE_UPDATE, CMD_GAME_OVER,
}


class ProtocolReader:
    """Leitor de mensagens com buffer persistente por conexao.

    Garante que mensagens sejam extraidas uma por vez, mesmo quando
    multiplas mensagens chegam em unico recv(). O buffer interno
    preserva dados nao consumidos entre chamadas.
    """

    def __init__(self):
        self._buffer = ""

    def recv_message(self, sock):
        """Le uma mensagem completa do socket. Retorna str ou None."""
        while True:
            # Tenta extrair uma mensagem do buffer atual
            msg, restante = self._extract_one()
            if msg is not None:
                self._buffer = restante
                return msg

            # Precisa de mais dados
            try:
                chunk = sock.recv(4096).decode(ENCODING)
                if not chunk:
                    return None
                self._buffer += chunk
            except socket.timeout:
                raise
            except Exception:
                return None

    def _extract_one(self):
        """Tenta extrair exatamente 1 mensagem do buffer interno.

        Retorna (mensagem, restante) ou (None, buffer_original).
        """
        first = self._buffer.find(DELIMITER)
        if first == -1:
            return None, self._buffer

        header_line = self._buffer[:first]
        cmd = header_line.split(" ", 1)[0]

        if cmd in COMMANDS_WITH_PAYLOAD:
            # Precisa de 2o \r\n (payload JSON)
            rest = self._buffer[first + 2:]
            second = rest.find(DELIMITER)
            if second == -1:
                return None, self._buffer
            end = first + 2 + second + 2
            return self._buffer[:end], self._buffer[end:]
        else:
            # So o cabecalho (1 \r\n)
            return self._buffer[:first + 2], self._buffer[first + 2:]


# Funcao legada — mantida para compatibilidade com testes existentes.
# Novos codigos devem usar ProtocolReader.
_recv_buffers = {}

def recv_message(sock):
    """Le do socket ate receber mensagem completa. Retorna str ou None."""
    fd = sock.fileno()
    buffer = _recv_buffers.pop(fd, "")
    reader = ProtocolReader()
    reader._buffer = buffer
    result = reader.recv_message(sock)
    sobra = reader._buffer
    if sobra:
        _recv_buffers[fd] = sobra
    return result
