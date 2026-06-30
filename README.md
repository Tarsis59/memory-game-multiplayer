# Memory Game — Jogo da Memoria Multiplayer via TCP

## Proposito da Aplicacao

O Memory Game e um jogo da memoria multiplayer distribuido.
Dois jogadores se conectam ao servidor atraves de dois terminais
separados (dois clientes) e jogam em turnos alternados.
O servidor funciona como arbitro: controla o tabuleiro,
valida cada jogada, detecta pares, atualiza o placar e
declara o vencedor ao final.

O tabuleiro possui 16 posicoes (4x4) com 8 pares de cartas
embaralhadas. A cada turno, o jogador vira duas cartas:
se forem iguais, marca ponto e joga de novo; se nao,
as cartas voltam a ficar ocultas e o turno passa para
o adversario. Vence quem encontrar mais pares.

## Destaques Técnicos:

* **Multiplexação (Chat + Jogo):** A aplicação possui um Chat em Tempo Real embutido, o que demonstra a capacidade do protocolo construído de multiplexar eventos síncronos (turnos do jogo) e assíncronos (mensagens de texto) através do mesmo socket TCP de forma não-bloqueante.
* **Dual-Stack IPv4 e IPv6:** O servidor e o cliente possuem suporte inteligente e transparente para conexões simultâneas em IPv4 (redes locais/NAT) e IPv6 (internet global P2P), utilizando resolução de endereços moderna.
* **Separação de Camadas (MVC):** A lógica de rede está totalmente desacoplada da interface. O cliente exibe um instalador interativo em terminal (Curses) para o *handshake* inicial e transfere o controle para um motor gráfico independente a 60 FPS (Pygame) para renderizar a partida, sem que uma thread bloqueie a outra.

---

## Motivacao pela Escolha do TCP

| Criterio | TCP | UDP |
|---|---|---|
| Entrega garantida | Sim | Nao |
| Ordem das mensagens | Garantida | Nao garantida |
| Controle de fluxo | Sim | Nao |
| Conexao orientada | Sim | Nao |

Em um jogo por turnos, a **ordem e a entrega garantida de mensagens
sao essenciais**: uma carta revelada fora de ordem ou perdida
corrompe o estado do jogo nos dois clientes. O overhead do TCP e
desprezivel dado o volume de dados do jogo, tornando-o a unica
escolha correta para esta aplicacao.

---

## Requisitos Mínimos

- Python 3.8 ou superior
- Rede TCP/IP funcional (funciona em localhost, rede local IPv4 ou Internet IPv6)
- Biblioteca Gráfica Pygame

**Instalação das dependências:**
Antes de executar o cliente, instale a biblioteca gráfica do jogo:
```bash
pip install pygame
```

**Nota para Windows:** Se desejar a interface grafica no terminal
(com setas e cores), instale o pacote opcional:
```bash
pip install windows-curses
```
Sem ele, o cliente funciona normalmente no modo fallback (console).

---

## Como Executar

### 1. Verificar Python

```bash
python --version
```

### 2. Terminal 1 — Iniciar o servidor

```bash
cd memory-game
python server/server.py
```

Saida esperada:
```
 Modo: Dual-Stack (IPv4 e IPv6)
 Porta: 9000
 -> Para jogar neste PC, o cliente liga em: localhost
 -> Para jogar na mesma rede, o cliente liga em: 172.26.19.141
==================================================
[SERVER] A aguardar por 2 jogadores...
```

### 3. Terminal 2 — Primeiro jogador

```bash
cd memory-game
python client/client.py 
```

### 4. Terminal 3 — Segundo jogador

```bash
cd memory-game
python client/client.py 
```

### 5. Jogando

Ao iniciar o `client.py`, um **Menu Interativo** aparecerá no terminal. 
1. Use as **SETAS** do teclado para escolher o tipo de conexão (Local, IPv4 ou IPv6) e aperte **ENTER**.
2. Digite o seu apelido e o IP fornecido pelo servidor (Se for local, não irá precisar).
3. Após a conexão, o terminal ficará em segundo plano e a **Janela Gráfica do Jogo** (Pygame) se abrirá!

**Controles dentro do Jogo:**
* Utilize o **Mouse (Botão Esquerdo)** para interagir com o tabuleiro. As cartas possuem efeito tátil de elevação (*hover*) quando é o seu turno.
* Para utilizar o **Chat em tempo real**, clique na barra inferior (ou pressione **T**), digite sua mensagem e aperte **ENTER**.
* Pressione **ESC** ou **Q** para sair da partida.

<img width="996" height="680" alt="print_ylo" src="https://github.com/user-attachments/assets/ce7b7f74-0f41-49a3-afc4-bee8d10782b6" />

### 6. Rodar testes do protocolo

```bash
python tests/test_protocol.py
```

### 7. Rodar demo automatizada

```bash
python tests/run_demo.py
```

---

## Heartbeat (PING / PONG)

O servidor monitora a conectividade dos jogadores a cada 10 segundos.
Conexões inativas por mais de 60 segundos sao automaticamente
fechadas, garantindo que uma queda de rede nao trave a partida.

| Mensagem | Direcao | Descricao |
|---|---|---|
| `PING` | S->C | Verificacao de conectividade |
| `PONG` | C->S | Resposta ao heartbeat |

---

## Protocolo MGAME/1.0

### Formato das Mensagens

```
COMANDO ARGUMENTO\r\n
[JSON_PAYLOAD]\r\n   <- presente apenas quando ha dados estruturados
```

### Tabela de Mensagens (22 mensagens)

| Mensagem | Direcao | Descricao |
|---|---|---|
| `JOIN <apelido>` | C->S | Jogador entra na partida |
| `OK WAITING` | S->C | Aguardando 2 jogador |
| `ERR NAME_TAKEN` | S->C | Apelido ja em uso |
| `GAME_START` + JSON | S->C | Jogo comeca; envia tabuleiro oculto |
| `YOUR_TURN` | S->C | E a sua vez |
| `WAIT_TURN <nome>` | S->C | Vez do adversario |
| `FLIP <pos>` | C->S | Vira carta na posicao |
| `ERR NOT_YOUR_TURN` | S->C | Nao e sua vez |
| `ERR INVALID_POS` | S->C | Posicao fora do intervalo |
| `ERR ALREADY_OPEN` | S->C | Carta ja revelada permanentemente |
| `CARD_REVEALED` + JSON | S->C | Carta virada (broadcast) |
| `MATCH` + JSON | S->C | Par encontrado (broadcast) |
| `NO_MATCH` + JSON | S->C | Sem par, cartas voltam (broadcast) |
| `SCORE_UPDATE` + JSON | S->C | Placar atualizado (broadcast) |
| `GAME_OVER` + JSON | S->C | Fim de jogo + vencedor |
| `QUIT` | C->S | Abandona a partida |
| `PLAYER_LEFT <nome>` | S->C | Adversario saiu |
| `BYE` | S->C | Confirmacao de saida |
| `PING` | S->C | Heartbeat: verificacao de conectividade |
| `PONG` | C->S | Heartbeat: resposta ao PING |
| `CHAT <msg>` | C->S | Jogador envia uma mensagem de texto no chat |
| `CHAT_MSG` + JSON | S->C | Broadcast da mensagem de chat (autor e texto) para a sala |

### Diagrama de Estados — Servidor

```text
                         +-------------------+
                         | AGUARDANDO        |
                         | JOGADORES         |
                         +--------+----------+
                                  |
                          2 jogadores conectados
                                  |
                                  v
                         +-------------------+
                         | INICIANDO JOGO    |---- envia GAME_START a ambos
                         +--------+----------+
                                  |
                                  v
    +------------------->+-------------------+
    |                    | TURNO ATUAL       |
    |                    +--------+----------+
    |                             |
    |                        FLIP 1 carta
    |                             |
    |                             v
    |                    +-------------------+
    |                    | AGUARDA 2 CARTA   |
    |                    +--------+----------+
    |                             |
    |                        FLIP 2 carta
    |                             |
    |                +------------+------------+
    |                |                         |
    |                v                         v
    |       +-------------------+   +-------------------+
    |       | PAR_CERTO         |   | SEM_PAR           |
    |       | pontua jogador    |   | inverte o turno   |
    |       +--------+----------+   +--------+----------+
    |                |                         |
    |          todas reveladas?                |
    |          /            \                  |
    |        NÃO            SIM                |
    |        /                \                |
    +-------+                  +---------------+
                               |
                               v
    (Qualquer momento)   +-------------------+
      Desconexão ------> | GAME_OVER         |---- broadcast resultado
                         +-------------------+

*Nota: Eventos de CHAT e PING/PONG ocorrem de forma assíncrona e não interferem na máquina de estados principal do jogo.
```

### Diagrama de Estados — Cliente

```text
+-------------------+
| OFFLINE (Menu)    |---- Escolhe rede e conecta (TCP)
+--------+----------+
         |
         v
+-------------------+
| JOINING           |---- Envia JOIN <nome>
+--------+----------+
         |
         v
+-------------------+
| WAITING_OPPONENT  |---- Recebe OK WAITING
+--------+----------+
         |
    GAME_START
         |
         v
+-------------------+
| IN_GAME           | <---------------------------+
+--------+----------+                             |
         |                                        |
    +----+----+                                   |
    |         |                                   |
    v         v                                   |
+--------+  +--------+                            |
|MY_TURN |  |OPP_TURN|                            |
|FLIP n  |  |aguarda |                            |
+--------+  +--------+                            |
    |         |                                   |
    +----+----+                                   |
         |                                        |
    CARD_REVEALED                                 |
    MATCH / NO_MATCH                              |
    SCORE_UPDATE                                  |
         |                                        |
         +----------------------------------------+
         |
     GAME_OVER ou PLAYER_LEFT
         |
         v
+-------------------+
| POPUP FIM DE JOGO |---- Aguarda jogador pressionar ENTER
+--------+----------+
         |
         v
+-------------------+
| OFFLINE / FECHA   |---- Envia QUIT e encerra Pygame
+-------------------+
```

### Exemplo de Sessao Completa

```
Ylo -> Servidor:  JOIN Ylo\r\n
Servidor -> Ylo:  OK WAITING\r\n

Tarsis -> Servidor:    JOIN Tarsis\r\n
Servidor -> Tarsis:    OK WAITING\r\n

Servidor -> Ylo:  GAME_START \r\n
                    {"board_size":16,"players":["Ylo","Tarsis"],"hidden":["?",...]}\r\n
Servidor -> Tarsis:    GAME_START \r\n (mesma mensagem)

Servidor -> Ylo:  YOUR_TURN\r\n
Servidor -> Tarsis:    WAIT_TURN Ylo\r\n

Ylo -> Servidor:  FLIP 3\r\n
Servidor -> todos:  CARD_REVEALED {"pos":3,"symbol":"A","player":"Ylo"}\r\n

Ylo -> Servidor:  FLIP 11\r\n
Servidor -> todos:  CARD_REVEALED {"pos":11,"symbol":"A",...}\r\n
Servidor -> todos:  MATCH {"positions":[3,11],"symbol":"A","player":"Ylo"}\r\n
Servidor -> todos:  SCORE_UPDATE {"scores":{"Ylo":1,"Tarsis":0}}\r\n
Servidor -> Ylo:  YOUR_TURN\r\n (Ylo joga de novo por ter acertado)

...

Servidor -> todos:  GAME_OVER {"scores":{"Ylo":5,"Tarsis":3},"winner":"Ylo"}\r\n
```

---

## Estrutura de Arquivos

```
memory-game/
+-- shared/
|   +-- protocol.py      # Protocolo MGAME/1.0 (encode/decode/recv + ProtocolReader)
+-- server/
|   +-- server.py        # Servidor arbitro multi-thread com heartbeat
+-- client/
|   +-- client.py        # Cliente (Menu Wizard em Curses + Motor Gráfico em Pygame)
+-- tests/
|   +-- test_protocol.py # Testes unitarios do protocolo
|   +-- test_full_game.py# Teste de integracao (2 FLIPs de Ylo)
|   +-- run_demo.py      # Demo automatica server + 2 clients
+-- README.md
+-- requirements.txt
+-- .gitignore
```

---

## Mapa do Código — Guia de Referência para Apresentação

> Seção criada para responder rapidamente as perguntas do professor sobre onde cada conceito foi implementado.

### Tabela de Referência Rápida

| Pergunta do Professor | Arquivo | Linhas |
|---|---|---|
| Onde o socket TCP é criado? | `server/server.py` | 336–340 |
| Onde o cliente conecta via TCP? | `client/client.py` | 497–499 |
| Como o protocolo empacota mensagens? | `shared/protocol.py` | 44–71 |
| Como trata fragmentação TCP? | `shared/protocol.py` | 79–124 |
| Como aceita múltiplos clientes? | `server/server.py` | 359–366 |
| Como o heartbeat detecta queda? | `server/server.py` | 72–101 |
| Onde fica a lógica de turnos? | `server/server.py` | 245–309 |
| Como o broadcast é enviado? | `server/server.py` | 57–62 |
| Como o chat multiplexa no TCP? | `server/server.py` | 177–183 |
| Onde as 22 mensagens são definidas? | `shared/protocol.py` | 11–41 |
| Como o cliente processa eventos? | `client/client.py` | 61–181 |
| Como a interface gráfica roda? | `client/client.py` | 225–395 |
| Como funciona o Dual-Stack? | `server/server.py` | 336–341 |
| Como o vencedor é declarado? | `server/server.py` | 311–319 |

---

### 1. Onde o Socket TCP é Criado no Servidor?

O servidor usa `socket.create_server()` que abstrai a criação do socket, bind e configuração. Quando o sistema suporta Dual-Stack (IPv4 + IPv6), usa `AF_INET6` com `dualstack_ipv6=True`; caso contrário, cria socket IPv4 puro.

**Arquivo:** `server/server.py` — Linhas **336–340**
```python
def main():
    if hasattr(socket, 'has_dualstack_ipv6') and socket.has_dualstack_ipv6():
        srv = socket.create_server((HOST, PORT), family=socket.AF_INET6, dualstack_ipv6=True)
        modo = "Dual-Stack (IPv4 e IPv6)"
    else:
        srv = socket.create_server((HOST, PORT))
        modo = "Apenas IPv4"
    srv.listen(2)
```

As constantes de host e porta estão nas linhas 32–33:
```python
HOST = ""   # Escuta em todas as interfaces
PORT = 9000
```

---

### 2. Onde o Cliente Conecta via TCP?

O cliente usa `socket.create_connection()`, que resolve automaticamente IPv4 ou IPv6 baseado no endereço fornecido, e aplica timeout de 5 segundos na conexão.

**Arquivo:** `client/client.py` — Linhas **497–499**
```python
try:
    sock = socket.create_connection((server_ip, PORT), timeout=5)
    sock.settimeout(None)
except OSError as e:
    print(f"\n[ERRO] Não foi possível ligar a {server_ip}:{PORT}.")
    return
```

O IP do servidor é escolhido pelo usuário no menu interativo (Local = `localhost`,
IPv4 = IP digitado, IPv6 = IP digitado) — linhas **450–493**.

---

### 3. Como o Protocolo Empacota e Desempacota Mensagens?

O formato é textual: `COMANDO ARGUMENTO\r\n[JSON_PAYLOAD\r\n]`. O `encode()` monta os bytes e o `decode()` faz o parse reverso.

**Arquivo:** `shared/protocol.py` — Linhas **44–71**
```python
def encode(command: str, arg: str = "", payload: dict = None) -> bytes:
    line = command
    if arg:
        line += f" {arg}"
    line += DELIMITER
    if payload is not None:
        line += json.dumps(payload, ensure_ascii=False) + DELIMITER
    return line.encode(ENCODING)

def decode(raw: str):
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
```

---

### 4. Como o ProtocolReader Lida com a Fragmentação TCP?

O TCP não preserva limites de mensagem — um único `recv()` pode trazer zero, uma ou várias mensagens. O `ProtocolReader` mantém um **buffer persistente por conexão** e extrai exatamente **1 mensagem por chamada**, devolvendo o resto para a próxima.

**Arquivo:** `shared/protocol.py` — Linhas **79–124**

```python
class ProtocolReader:
    def __init__(self):
        self._buffer = ""

    def recv_message(self, sock):
        while True:
            msg, restante = self._extract_one()
            if msg is not None:
                self._buffer = restante
                return msg
            chunk = sock.recv(4096).decode(ENCODING)
            if not chunk:
                return None
            self._buffer += chunk

    def _extract_one(self):
        first = self._buffer.find(DELIMITER)
        if first == -1:
            return None, self._buffer
        header_line = self._buffer[:first]
        cmd = header_line.split(" ", 1)[0]
        if cmd in COMMANDS_WITH_PAYLOAD:
            rest = self._buffer[first + 2:]
            second = rest.find(DELIMITER)
            if second == -1:
                return None, self._buffer
            end = first + 2 + second + 2
            return self._buffer[:end], self._buffer[end:]
        else:
            return self._buffer[:first + 2], self._buffer[first + 2:]
```

A constante `COMMANDS_WITH_PAYLOAD` (linhas 73–76) define quais comandos possuem corpo JSON e precisam do segundo `\r\n`:
```python
COMMANDS_WITH_PAYLOAD = {
    CMD_GAME_START, CMD_CARD_REVEALED, CMD_MATCH,
    CMD_NO_MATCH, CMD_SCORE_UPDATE, CMD_GAME_OVER, CMD_CHAT_MSG
}
```

---

### 5. Como o Servidor Aceita Múltiplos Clientes Simultaneamente?

Cada cliente conectado ganha uma **thread dedicada** (`threading.Thread`). O servidor aceita 2 jogadores simultaneamente sem bloquear.

**Arquivo:** `server/server.py` — Linhas **359–366**
```python
while True:
    try:
        conn, addr = srv.accept()
        t = threading.Thread(target=handle_client, args=(conn, addr), daemon=True)
        t.start()
    except KeyboardInterrupt:
        print("\n[SERVER] A encerrar.")
        break
```

A função `handle_client` (linha 103) processa: JOIN, aguarda 2o jogador, loop de jogo
(FLIP, QUIT, CHAT, PONG).

---

### 6. Como o Heartbeat Detecta Queda de Conexão?

Uma **thread separada** (`monitor_heartbeats`) a cada 10s envia `PING` para cada jogador. Se passar **60 segundos** sem resposta (`PONG`), a conexão é fechada. O heartbeat **só monitora durante jogo ativo** — enquanto aguarda 2o jogador, não desconecta.

**Arquivo:** `server/server.py` — Linhas **72–101**

```python
def monitor_heartbeats():
    while True:
        time.sleep(10)
        now = time.time()
        stale_connections = []
        with room.lock:
            if not room.started:
                continue              # só durante jogo ativo
            for p in list(room.players):
                name = p["name"]
                last = room.last_seen.get(name, now)
                if now - last > 60:   # 60s sem resposta
                    stale_connections.append(p)
                else:
                    try:
                        conn.sendall(encode(CMD_PING))
                    except Exception:
                        pass
        for p in stale_connections:    # fecha FORA do lock
            try:
                p["conn"].close()
            except Exception:
                pass
```

**Cliente responde ao PING** — `client/client.py` — Linhas **77–80**:
```python
if command == CMD_PING:
    try: sock.sendall(encode(CMD_PONG))
    except OSError: pass
    continue
```

---

### 7. Onde Fica a Lógica de Turnos?

A função `_handle_flip()` concentra toda a lógica: valida turno, primeira carta, segunda carta, MATCH (pontua + joga de novo) ou NO_MATCH (passa turno), verifica fim de jogo.

**Arquivo:** `server/server.py` — Linhas **245–309**

```python
def _handle_flip(player_name: str, arg: str, conn):
    game_ended = False
    with room.lock:
        # 1. Valida se é o turno do jogador
        if room.players[room.current_turn]["name"] != player_name:
            conn.sendall(encode(CMD_ERR, ERR_NOT_YOUR_TURN))
            return
        # 2. Valida posição (0 a 15)
        try:
            pos = int(arg)
            assert 0 <= pos < BOARD_SIZE
        except (ValueError, AssertionError):
            conn.sendall(encode(CMD_ERR, ERR_INVALID_POS))
            return
        # 3. Valida se carta já foi revelada
        if room.revealed[pos]:
            conn.sendall(encode(CMD_ERR, ERR_ALREADY_OPEN))
            return

        symbol = room.board[pos]
        room.broadcast(encode(CMD_CARD_REVEALED, "", {
            "pos": pos, "symbol": symbol, "player": player_name,
        }))
        # 4. Primeira carta do turno
        if room.first_flip is None:
            room.first_flip = (pos, symbol)
            return
        # 5. Segunda carta: MATCH ou NO_MATCH
        first_pos, first_symbol = room.first_flip
        room.first_flip = None
        if first_symbol == symbol:
            room.revealed[first_pos] = True
            room.revealed[pos] = True
            for p in room.players:
                if p["name"] == player_name:
                    p["score"] += 1
            # broadcast MATCH + SCORE_UPDATE
            if room.all_revealed():
                game_ended = True
        else:
            room.current_turn = 1 - room.current_turn    # passa turno
    if game_ended:
        _end_game()
        return
    _notify_turn()
```

A notificação de turno (linhas 228–243) envia `YOUR_TURN` para o atual e `WAIT_TURN` para o outro:
```python
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
```

---

### 8. Como o Broadcast é Enviado para Ambos os Jogadores?

`GameRoom.broadcast()` itera sobre `self.players` e envia os mesmos dados para cada conexão.

**Arquivo:** `server/server.py` — Linhas **57–62**
```python
def broadcast(self, data: bytes):
    for p in self.players:
        try:
            p["conn"].sendall(data)
        except Exception:
            pass
```

---

### 9. Como o Chat Multiplexa no Mesmo Socket TCP?

Novos comandos `CHAT` (C→S) e `CHAT_MSG` (S→C). O servidor retransmite a mensagem para ambos via broadcast. Como o `ProtocolReader` separa múltiplas mensagens no buffer TCP, o chat nunca corrompe o estado do jogo.

**Servidor** — `server/server.py` — Linhas **177–183**:
```python
elif command == CMD_CHAT:
    msg_text = arg.strip()
    if msg_text:
        room.broadcast(encode(CMD_CHAT_MSG, "", {
            "player": player_name,
            "msg": msg_text
        }))
```

**Cliente** — `client/client.py` — Linhas **82–86**:
```python
if command == CMD_CHAT_MSG and payload:
    msg_formatada = f"{payload['player']}: {payload['msg']}"
    chat_history.append(msg_formatada)
    if len(chat_history) > 6:
        chat_history.pop(0)
```

O chat é **assíncrono** — o `if CMD_CHAT_MSG` no receiver não interfere nos `elif` dos comandos de jogo.

---

### 10. Como a Thread Receiver do Cliente Processa os Eventos?

Uma thread em background executa um loop infinito: recebe → decodifica → atualiza estado global.

**Arquivo:** `client/client.py` — Linhas **61–181**

```python
def receiver(sock):
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

        if command == CMD_PING:                      # Heartbeat
            try: sock.sendall(encode(CMD_PONG))
            except OSError: pass
            continue
        if command == CMD_CHAT_MSG and payload:       # Chat
            chat_history.append(...)
        elif command == CMD_OK and arg == "WAITING":  # Aguardando
            set_status("Aguardar pelo 2º jogador...", "info")
        elif command == CMD_GAME_START and payload:   # Início
            # reinicia tabuleiro
        elif command == CMD_YOUR_TURN:                # Sua vez
            my_turn = True
        elif command == CMD_CARD_REVEALED:            # Carta virada
            board[pos] = symbol
        elif command == CMD_MATCH:                    # Par!
            revealed[pos] = True
        elif command == CMD_NO_MATCH:                 # Errou
            time.sleep(2.5)
            board[pos] = "?"
        elif command == CMD_SCORE_UPDATE:             # Placar
            scores.update(...)
        elif command == CMD_GAME_OVER:                # Fim!
            game_over = True
```

---

### 11. Como a Interface Gráfica (Pygame) se Integra com a Rede?

Loop principal a **60 FPS**: lê eventos do mouse/teclado → envia comandos via socket → renderiza tabuleiro + painel + chat.

**Arquivo:** `client/client.py` — Linhas **225–395**

```python
running = True
while running:
    mouse_pos = pygame.mouse.get_pos()
    for event in pygame.event.get():
        if event.type == pygame.MOUSEBUTTONDOWN:
            if my_turn:                              # clique no tabuleiro
                for row in range(4):
                    for col in range(4):
                        card_rect = pygame.Rect(cx, cy, 110, 120)
                        if card_rect.collidepoint(event.pos):
                            sock.sendall(encode(CMD_FLIP, str(idx)))
            if event.pos[0] > 620:                   # clique no chat
                is_typing = True
        elif event.type == pygame.KEYDOWN:
            if is_typing:
                if event.key == pygame.K_RETURN:     # envia chat
                    sock.sendall(encode(CMD_CHAT, chat_buffer.strip()))
                elif event.key == pygame.K_BACKSPACE:
                    chat_buffer = chat_buffer[:-1]
            elif event.key == pygame.K_q:             # sai
                running = False

    screen.fill(BG_COLOR)
    # Desenha 16 cartas com sombra + hover + símbolos coloridos
    # Desenha painel lateral: placar, status, chat

    pygame.display.flip()
    clock.tick(60)
```

---

### 12. Como Funciona o Dual-Stack IPv4 + IPv6?

Detecta `has_dualstack_ipv6()`. Se suportado, cria socket IPv6 que aceita conexões IPv4 e IPv6. Senão, cria socket IPv4 puro.

**Arquivo:** `server/server.py` — Linhas **336–341**
```python
if hasattr(socket, 'has_dualstack_ipv6') and socket.has_dualstack_ipv6():
    srv = socket.create_server((HOST, PORT), family=socket.AF_INET6, dualstack_ipv6=True)
    modo = "Dual-Stack (IPv4 e IPv6)"
else:
    srv = socket.create_server((HOST, PORT))
    modo = "Apenas IPv4"
```

O servidor também descobre e exibe seu IP automaticamente (linhas 322–333):
```python
def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP
```

---

### 13. Onde o Vencedor é Declarado?

Quando todas as cartas estão reveladas ou um jogador desconecta, `_end_game()` calcula e declara.

**Arquivo:** `server/server.py` — Linhas **311–319**
```python
def _end_game():
    scores = {p["name"]: p["score"] for p in room.players}
    s = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    winner = s[0][0] if s[0][1] != s[1][1] else "EMPATE"
    room.broadcast(encode(CMD_GAME_OVER, "", {
        "scores": scores,
        "winner": winner,
    }))
```

Proteção contra dupla declaração por desconexão (linhas 199–210):
```python
if not room.all_revealed():
    remaining = room.other_player(player_name)
    if remaining:
        # envia GAME_OVER para o jogador restante
```

---

### 14. Onde os Erros do Protocolo São Tratados?

**Constantes** — `shared/protocol.py` — Linhas **37–41**:
```python
ERR_NAME_TAKEN    = "NAME_TAKEN"
ERR_NOT_YOUR_TURN = "NOT_YOUR_TURN"
ERR_INVALID_POS   = "INVALID_POS"
ERR_ALREADY_OPEN  = "ALREADY_OPEN"
```

**Validação** — `server/server.py` — Linhas **248–264**:
```python
if room.players[room.current_turn]["name"] != player_name:
    conn.sendall(encode(CMD_ERR, ERR_NOT_YOUR_TURN))
try:
    pos = int(arg)
    assert 0 <= pos < BOARD_SIZE
except (ValueError, AssertionError):
    conn.sendall(encode(CMD_ERR, ERR_INVALID_POS))
if room.revealed[pos]:
    conn.sendall(encode(CMD_ERR, ERR_ALREADY_OPEN))
```

**Exibição** — `client/client.py` — Linhas **176–177**:
```python
elif command == CMD_ERR:
    set_status(f"ERRO: {arg}", "error")
```

---

### 15. Onde as 22 Mensagens do Protocolo São Definidas?

**Arquivo:** `shared/protocol.py` — Linhas **11–41**

```python
# Cliente -> Servidor (5)
CMD_JOIN = "JOIN"; CMD_FLIP = "FLIP"; CMD_QUIT = "QUIT"
CMD_PONG = "PONG"; CMD_CHAT = "CHAT"

# Servidor -> Cliente (17)
CMD_OK = "OK"; CMD_ERR = "ERR"; CMD_GAME_START = "GAME_START"
CMD_YOUR_TURN = "YOUR_TURN"; CMD_WAIT_TURN = "WAIT_TURN"
CMD_CARD_REVEALED = "CARD_REVEALED"; CMD_MATCH = "MATCH"
CMD_NO_MATCH = "NO_MATCH"; CMD_SCORE_UPDATE = "SCORE_UPDATE"
CMD_GAME_OVER = "GAME_OVER"; CMD_PLAYER_LEFT = "PLAYER_LEFT"
CMD_BYE = "BYE"; CMD_PING = "PING"; CMD_CHAT_MSG = "CHAT_MSG"

# Args e Erros (6)
ARG_WAITING = "WAITING"
ERR_NAME_TAKEN = "NAME_TAKEN"; ERR_NOT_YOUR_TURN = "NOT_YOUR_TURN"
ERR_INVALID_POS = "INVALID_POS"; ERR_ALREADY_OPEN = "ALREADY_OPEN"
```

---

## Autores

- Tarsis Carvalho Barreto
- Ylo Silva de Sá Bittencourt
- Henrique Barreto Pereira
- Thiago Pereira

## Licenca

MIT
