import streamlit as st
from supabase import create_client, Client
import time, random, datetime, json

# ==========================================
# 1. SUPABASE SETUP
# ==========================================
SUPABASE_URL = "https://gxdpjxpzyivzlvwyfaoj.supabase.co"
SUPABASE_KEY = "sb_publishable_TQWFXwkHlR90wtnp50z0Dg_zGHKpo5g"

@st.cache_resource
def init_supabase() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)
supabase = init_supabase()

st.set_page_config(page_title="Grid Clash", page_icon="🎮", layout="centered")

# ==========================================
# 2. CSS (Floating Emojis + Game UI)
# ==========================================
st.markdown("""
<style>
@keyframes floatUp {
    0%   { transform: translateY(0px) scale(1); opacity: 1; }
    100% { transform: translateY(-400px) scale(1.5); opacity: 0; }
}
.floating-emoji {
    position: fixed;
    bottom: 10%;
    font-size: 3rem;
    animation: floatUp 4s ease-out forwards;
    pointer-events: none;
    z-index: 9999;
}
.hero { text-align:center; padding: 40px 20px; background: linear-gradient(135deg,#6a11cb 0%,#2575fc 100%); border-radius: 20px; color: white; margin-bottom: 24px; }
.name-tag { display:inline-block; padding: 6px 14px; border-radius: 999px; background: #eef2ff; color: #3730a3; font-weight: 600; margin: 4px 0; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 3. AI LOGIC (Minimax)
# ==========================================
def check_win(b, sym):
    for i in range(3):
        if all(b[i][j] == sym for j in range(3)): return True
        if all(b[j][i] == sym for j in range(3)): return True
    if all(b[i][i] == sym for i in range(3)): return True
    if all(b[i][2-i] == sym for i in range(3)): return True
    return False

def get_ai_move(board, ai_sym, difficulty="hard"):
    human_sym = "X" if ai_sym == "O" else "O"
    empties = [(r, c) for r in range(3) for c in range(3) if board[r][c] == "."]
    if not empties: return None
    if difficulty == "easy": return random.choice(empties)
    
    def minimax(b, depth, is_max, alpha, beta):
        if check_win(b, ai_sym): return 10 - depth
        if check_win(b, human_sym): return -10 + depth
        if all(b[r][c] != "." for r in range(3) for c in range(3)): return 0
        
        if is_max:
            best = -float("inf")
            for r in range(3):
                for c in range(3):
                    if b[r][c] == ".":
                        b[r][c] = ai_sym
                        val = minimax(b, depth + 1, False, alpha, beta)
                        b[r][c] = "."
                        best = max(best, val); alpha = max(alpha, best)
                        if beta <= alpha: break
            return best
        else:
            best = float("inf")
            for r in range(3):
                for c in range(3):
                    if b[r][c] == ".":
                        b[r][c] = human_sym
                        val = minimax(b, depth + 1, True, alpha, beta)
                        b[r][c] = "."
                        best = min(best, val); beta = min(beta, best)
                        if beta <= alpha: break
            return best

    best_score = -float("inf"); best_move = None
    for r, c in empties:
        board[r][c] = ai_sym
        score = minimax(board, 0, False, -float("inf"), float("inf"))
        board[r][c] = "."
        if score > best_score:
            best_score = score; best_move = (r, c)
    return best_move

# ==========================================
# 4. EMOJI FUNCTIONS
# ==========================================
def send_emoji(emoji_char):
    try: supabase.table("emojis").insert({"emoji": emoji_char}).execute()
    except Exception: pass

def get_recent_emojis():
    try:
        now = datetime.datetime.now(datetime.timezone.utc)
        five_secs_ago = now - datetime.timedelta(seconds=5)
        response = supabase.table("emojis").select("*").gte("created_at", five_secs_ago.isoformat()).order("created_at").execute()
        return response.data
    except Exception: return []

# ==========================================
# 5. GAME LOGIC (Supabase)
# ==========================================
if "difficulty" not in st.session_state: st.session_state.difficulty = "hard"
if "in_game" not in st.session_state: st.session_state.in_game = False

def reset_game():
    empty_board = [[".", ".", "."], [".", ".", "."], [".", ".", "."]]
    supabase.table("game_state").update({"board": empty_board, "turn": "X", "winner": None}).eq("id", 1).execute()

def landing():
    st.markdown("<div class='hero'><h1>🎮 GRID CLASH</h1><p>Play vs the AI.</p></div>", unsafe_allow_html=True)
    
    diff = st.radio("Difficulty", ["easy", "medium", "hard"], horizontal=True, index=2)
    st.session_state.difficulty = diff
    
    if st.button("🚀 Start Game", use_container_width=True, type="primary"):
        reset_game()
        st.session_state.in_game = True
        st.rerun()

@st.fragment(run_every=1.0)
def game_fragment():
    # 1. Render Floating Emojis
    recent_emojis = get_recent_emojis()
    html_output = ""
    for row in recent_emojis:
        emoji = row.get("emoji")
        if emoji:
            left_pos = random.randint(10, 90)
            html_output += f'<div class="floating-emoji" style="left: {left_pos}vw;">{emoji}</div>'
    if html_output: st.markdown(html_output, unsafe_allow_html=True)

    # 2. Fetch Game State
    res = supabase.table("game_state").select("*").eq("id", 1).execute()
    if not res.data: 
        st.error("Could not load game.")
        return
    game = res.data[0]
    board = game["board"]

    st.markdown("**You:** 🧑 You (X)  |  **Opponent:** 🤖 AI (O)", unsafe_allow_html=True)
    
    if game["winner"]:
        st.success(f"🏆 Winner: {game['winner']}")
    else:
        st.write(f"Turn: **{game['turn']}**")

    # 3. Render Board
    my_turn = (game["turn"] == "X" and not game["winner"])
    for r in range(3):
        cols = st.columns(3)
        for c in range(3):
            cell = board[r][c]
            if cols[c].button("·" if cell == "." else cell, key=f"c{r}{c}", use_container_width=True, disabled=not my_turn or cell != "."):
                # Player Move
                board[r][c] = "X"
                winner = "X" if check_win(board, "X") else ("draw" if all(cell != "." for row in board for cell in row) else None)
                supabase.table("game_state").update({"board": board, "turn": "O" if not winner else "X", "winner": winner}).eq("id", 1).execute()
                st.rerun()

    # 4. AI Move
    if game["turn"] == "O" and not game["winner"]:
        time.sleep(0.6) # Fake thinking delay
        ai_move = get_ai_move(board, "O", st.session_state.difficulty)
        if ai_move:
            r, c = ai_move
            board[r][c] = "O"
            winner = "O" if check_win(board, "O") else ("draw" if all(cell != "." for row in board for cell in row) else None)
            supabase.table("game_state").update({"board": board, "turn": "X" if not winner else "O", "winner": winner}).eq("id", 1).execute()
            st.rerun()

    st.divider()
    
    # 5. Emoji Reactions
    st.write("**Send a reaction:**")
    e1, e2, e3, e4 = st.columns(4)
    if e1.button("🔥", use_container_width=True): send_emoji("🔥")
    if e2.button("❤️", use_container_width=True): send_emoji("❤️")
    if e3.button("😂", use_container_width=True): send_emoji("😂")
    if e4.button("🚀", use_container_width=True): send_emoji("🚀")

    st.divider()
    if st.button("🚪 Exit to Lobby", use_container_width=True):
        st.session_state.in_game = False
        st.rerun()

# ==========================================
# 6. ROUTER
# ==========================================
if not st.session_state.in_game:
    landing()
else:
    game_fragment()
