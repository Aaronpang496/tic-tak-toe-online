# game_logic.py
import copy, random

EMPTY = "."
P1 = "X"
P2 = "O"
AI_ID = "__ai__"

HUMAN_NAMES = [
    "NeonFox", "SilentTiger", "CosmicOtter", "RapidPanda", "TurboWolf",
    "QuietFalcon", "LuckyBadger", "MightyKoala", "SwiftLynx", "BoldRaven",
    "PixelMoose", "EchoHawk", "ShadowGoat", "BrightNewt", "IronBunny",
]
AI_NAMES = ["Bot-Zeta", "Cortex-9", "NovaMind", "GlitchBot", "SynthCore",
            "Echo-7", "QuantumOwl", "PrimeBit"]
WIN_SCORE = 10

def pick_human_name(taken):
    pool = [n for n in HUMAN_NAMES if n not in taken]
    return random.choice(pool) if pool else f"Player{random.randint(100,999)}"

def pick_ai_name(taken):
    pool = [n for n in AI_NAMES if n not in taken]
    return random.choice(pool) if pool else "Bot"

def new_game():
    return {
        "board": [[EMPTY]*3 for _ in range(3)],
        "turn": P1,
        "winner": None,
        "players": [],
        "names": {},
        "moves": 0,
        "vs_ai": False,
        "ai_symbol": None,
        "ai_name": None,
        "ai_difficulty": "hard",
    }

def join(state, player_id, name=None):
    if player_id in state["players"] or len(state["players"]) >= 2:
        return state
    state["players"].append(player_id)
    state["names"][player_id] = name or pick_human_name(state["names"].values())
    return state

def leave(state, player_id):
    s = copy.deepcopy(state)
    if player_id in s["players"]:
        s["players"].remove(player_id)
        s["names"].pop(player_id, None)
    return s

def symbol_for(state, player_id):
    if player_id not in state["players"]:
        return None
    return P1 if state["players"].index(player_id) == 0 else P2

def start_ai_game(state, human_id, difficulty="hard"):
    s = copy.deepcopy(state)
    s["players"] = [human_id]
    s["vs_ai"] = True
    s["ai_symbol"] = P2
    s["ai_name"] = pick_ai_name(list(s["names"].values()))
    s["names"][AI_ID] = s["ai_name"]
    s["ai_difficulty"] = difficulty
    s["turn"] = P1
    return s

def apply_move(state, player_id, row, col):
    s = copy.deepcopy(state)
    if s["winner"] is not None:
        return s
    sym = symbol_for(s, player_id)
    if sym is None or sym != s["turn"]:
        return s
    if s["board"][row][col] != EMPTY:
        return s
    s["board"][row][col] = sym
    s["moves"] += 1
    _finish_or_pass(s, sym)
    return s

def apply_ai_move(state):
    s = copy.deepcopy(state)
    if not s["vs_ai"] or s["winner"] is not None or s["turn"] != s["ai_symbol"]:
        return s
    move = _pick_ai_move(s["board"], s["ai_symbol"], s.get("ai_difficulty", "hard"))
    if move is None:
        return s
    r, c = move
    s["board"][r][c] = s["ai_symbol"]
    s["moves"] += 1
    _finish_or_pass(s, s["ai_symbol"])
    return s

def _finish_or_pass(s, sym):
    if check_win(s["board"], sym):
        s["winner"] = sym
    elif s["moves"] == 9:
        s["winner"] = "draw"
    else:
        s["turn"] = P2 if s["turn"] == P1 else P1

def _pick_ai_move(board, ai_sym, difficulty="hard"):
    human_sym = P1 if ai_sym == P2 else P2
    b = [row[:] for row in board]
    empties = [(r, c) for r in range(3) for c in range(3) if b[r][c] == EMPTY]
    if not empties:
        return None
    if difficulty == "easy":
        return random.choice(empties)
    if difficulty == "medium" and random.random() < 0.5:
        return random.choice(empties)
    
    best_score = -float("inf")
    best_move = None
    order = [(1, 1), (0, 0), (0, 2), (2, 0), (2, 2), (0, 1), (1, 0), (1, 2), (2, 1)]
    ordered = [m for m in order if m in empties]
    for r, c in ordered:
        b[r][c] = ai_sym
        score = _minimax(b, 0, False, -float("inf"), float("inf"), ai_sym, human_sym)
        b[r][c] = EMPTY
        if score > best_score:
            best_score = score
            best_move = (r, c)
    return best_move

def _minimax(b, depth, is_max, alpha, beta, ai, human):
    if check_win(b, ai): return WIN_SCORE - depth
    if check_win(b, human): return -WIN_SCORE + depth
    if all(b[r][c] != EMPTY for r in range(3) for c in range(3)): return 0
    if is_max:
        best = -float("inf")
        for r in range(3):
            for c in range(3):
                if b[r][c] == EMPTY:
                    b[r][c] = ai
                    val = _minimax(b, depth + 1, False, alpha, beta, ai, human)
                    b[r][c] = EMPTY
                    best = max(best, val)
                    alpha = max(alpha, best)
                    if beta <= alpha: break
            if beta <= alpha: break
        return best
    else:
        best = float("inf")
        for r in range(3):
            for c in range(3):
                if b[r][c] == EMPTY:
                    b[r][c] = human
                    val = _minimax(b, depth + 1, True, alpha, beta, ai, human)
                    b[r][c] = EMPTY
                    best = min(best, val)
                    beta = min(beta, best)
                    if beta <= alpha: break
            if beta <= alpha: break
        return best

def check_win(b, sym):
    for i in range(3):
        if all(b[i][j] == sym for j in range(3)): return True
        if all(b[j][i] == sym for j in range(3)): return True
    if all(b[i][i] == sym for i in range(3)): return True
    if all(b[i][2-i] == sym for i in range(3)): return True
    return False
