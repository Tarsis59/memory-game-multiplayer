import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from shared.protocol import encode, decode


def check(name, condition):
    status = "PASS" if condition else "FAIL"
    print(f"  [{status}] {name}")
    assert condition, f"Teste falhou: {name}"


def test_join():
    raw = encode("JOIN", "Alice").decode()
    cmd, arg, payload = decode(raw)
    check("JOIN command", cmd == "JOIN")
    check("JOIN arg = Alice", arg == "Alice")
    check("JOIN sem payload", payload is None)


def test_flip():
    raw = encode("FLIP", "7").decode()
    cmd, arg, _ = decode(raw)
    check("FLIP command", cmd == "FLIP")
    check("FLIP arg = 7", arg == "7")


def test_game_start_payload():
    data = {"board_size": 16, "players": ["Alice", "Bob"], "hidden": ["?"] * 16}
    raw = encode("GAME_START", "", data).decode()
    cmd, arg, payload = decode(raw)
    check("GAME_START command", cmd == "GAME_START")
    check("GAME_START board_size", payload["board_size"] == 16)
    check("GAME_START players", payload["players"] == ["Alice", "Bob"])


def test_match_payload():
    data = {"positions": [3, 11], "symbol": "A", "player": "Alice"}
    raw = encode("MATCH", "", data).decode()
    cmd, _, payload = decode(raw)
    check("MATCH command", cmd == "MATCH")
    check("MATCH positions", payload["positions"] == [3, 11])
    check("MATCH symbol", payload["symbol"] == "A")


def test_ok_err():
    r1 = encode("OK", "WAITING").decode()
    r2 = encode("ERR", "NOT_YOUR_TURN").decode()
    c1, a1, _ = decode(r1)
    c2, a2, _ = decode(r2)
    check("OK WAITING", c1 == "OK" and a1 == "WAITING")
    check("ERR NOT_YOUR_TURN", c2 == "ERR" and a2 == "NOT_YOUR_TURN")


def test_game_over():
    data = {"scores": {"Alice": 5, "Bob": 3}, "winner": "Alice"}
    raw = encode("GAME_OVER", "", data).decode()
    cmd, _, payload = decode(raw)
    check("GAME_OVER command", cmd == "GAME_OVER")
    check("GAME_OVER winner", payload["winner"] == "Alice")
    check("GAME_OVER scores", payload["scores"]["Alice"] == 5)


if __name__ == "__main__":
    print("\n=== Testando protocolo MGAME/1.0 ===\n")
    test_join()
    test_flip()
    test_game_start_payload()
    test_match_payload()
    test_ok_err()
    test_game_over()
    print("\nOK - Todos os testes passaram!\n")
