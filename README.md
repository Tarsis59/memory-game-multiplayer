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

## Autores

- Tarsis Carvalho Barreto
- Ylo Silva de Sá Bittencourt

## Licenca

MIT
