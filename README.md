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

## Requisitos Minimos

- Python 3.8 ou superior
- Sem bibliotecas externas (apenas stdlib)
- Rede TCP/IP funcional (funciona em localhost ou rede local)
- 3 terminais: 1 servidor + 2 clientes

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
[SERVER] MGAME/1.0 aguardando jogadores em 0.0.0.0:9000...
```

### 3. Terminal 2 — Primeiro jogador

```bash
cd memory-game
python client/client.py Alice
```

### 4. Terminal 3 — Segundo jogador

```bash
cd memory-game
python client/client.py Bob
```

### 5. Jogando

Quando for sua vez, voce vera `SUA VEZ! Digite a posicao (0-15):`.
Digite o numero da posicao e pressione Enter.

```
     0    1    2    3
  +----+----+----+----+
0 |  ? |  ? |  ? |  ? |
  +----+----+----+----+
1 |  ? |  ? |  ? |  ? |
  +----+----+----+----+
2 |  ? |  ? |  ? |  ? |
  +----+----+----+----+
3 |  ? |  ? |  ? |  ? |
  +----+----+----+----+
```

### 6. Rodar testes do protocolo

```bash
python tests/test_protocol.py
```

### 7. Rodar demo automatizada

```bash
python tests/run_demo.py
```

---

## Protocolo MGAME/1.0

### Formato das Mensagens

```
COMANDO ARGUMENTO\r\n
[JSON_PAYLOAD]\r\n   <- presente apenas quando ha dados estruturados
```

### Tabela de Mensagens

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

### Diagrama de Estados — Servidor

```
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
                         +-------------------+
                         | TURNO_J1          |---- FLIP 1 carta
                         +--------+----------+
                                  |
                                  v
                         +-------------------+
                         | AGUARDA 2 CARTA   |
                         +--------+----------+
                                  |
                     +------------+------------+
                     |                         |
                     v                         v
            +-------------------+   +-------------------+
            | PAR_CERTO         |   | SEM_PAR           |
            | pontua J1         |   | passa turno       |
            +-------------------+   +-------------------+
                     |                         |
                     v                         v
            +-------------------+   +-------------------+
            | TURNO_J1          |   | TURNO_J2          |
            | (joga de novo)    |   |                   |
            +-------------------+   +-------------------+
                     |                         |
                     +---- todas cartas --------+
                                  |
                                  v
                         +-------------------+
                         | GAME_OVER         |---- broadcast resultado
                         +-------------------+
```

### Diagrama de Estados — Cliente

```
+-------------------+
| OFFLINE           |---- TCP connect
+--------+----------+
         |
         v
+-------------------+
| JOINING           |---- JOIN <nome>
+--------+----------+
         |
         v
+-------------------+
| WAITING_OPPONENT  |
+--------+----------+
         |
    GAME_START
         |
         v
+-------------------+
| IN_GAME           |
+--------+----------+
         |
    +----+----+
    |         |
    v         v
+--------+  +--------+
|MY_TURN |  |OPP_TURN|
|FLIP n  |  |aguarda |
+--------+  +--------+
    |         |
    +----+----+
         |
    CARD_REVEALED
    MATCH / NO_MATCH
    SCORE_UPDATE
         |
         v
+-------------------+
| IN_GAME (loop)    |---- ate GAME_OVER
+-------------------+
         |
         v
+-------------------+
| GAME_OVER         |---- OFFLINE
+-------------------+
```

### Exemplo de Sessao Completa

```
Alice -> Servidor:  JOIN Alice\r\n
Servidor -> Alice:  OK WAITING\r\n

Bob -> Servidor:    JOIN Bob\r\n
Servidor -> Bob:    OK WAITING\r\n

Servidor -> Alice:  GAME_START \r\n
                    {"board_size":16,"players":["Alice","Bob"],"hidden":["?",...]}\r\n
Servidor -> Bob:    GAME_START \r\n (mesma mensagem)

Servidor -> Alice:  YOUR_TURN\r\n
Servidor -> Bob:    WAIT_TURN Alice\r\n

Alice -> Servidor:  FLIP 3\r\n
Servidor -> todos:  CARD_REVEALED {"pos":3,"symbol":"A","player":"Alice"}\r\n

Alice -> Servidor:  FLIP 11\r\n
Servidor -> todos:  CARD_REVEALED {"pos":11,"symbol":"A",...}\r\n
Servidor -> todos:  MATCH {"positions":[3,11],"symbol":"A","player":"Alice"}\r\n
Servidor -> todos:  SCORE_UPDATE {"scores":{"Alice":1,"Bob":0}}\r\n
Servidor -> Alice:  YOUR_TURN\r\n (Alice joga de novo por ter acertado)

...

Servidor -> todos:  GAME_OVER {"scores":{"Alice":5,"Bob":3},"winner":"Alice"}\r\n
```

---

## Estrutura de Arquivos

```
memory-game/
+-- shared/
|   +-- protocol.py      # Protocolo MGAME/1.0 (encode/decode/recv)
+-- server/
|   +-- server.py        # Servidor arbitro multi-thread
+-- client/
|   +-- client.py        # Cliente (rodar 2x = 2 jogadores)
+-- tests/
|   +-- test_protocol.py # Testes unitarios do protocolo
|   +-- run_demo.py      # Demo automatica
+-- README.md
+-- requirements.txt
+-- .gitignore
```

---

## Autores

- [Seu Nome] - [Matricula]
- [Nome 2] - [Matricula]

## Licenca

MIT
