import streamlit as st
from supabase import create_client, Client
import asyncio, json, queue, threading, time, datetime, random
import websockets

# ==========================================
# 1. SETUP & CONNECTIONS
# ==========================================

# Supabase (Emojis)
SUPABASE_URL = "https://gxdpjxpzyivzlvwyfaoj.supabase.co"
SUPABASE_KEY = "sb_publishable_TQWFXwkHlR90wtnp50z0Dg_zGHKpo5g"

@st.cache_resource
def init_supabase() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)
supabase = init_supabase()

# WebSocket (Game)
# ⚠️ MAKE SURE THIS IS YOUR RENDER URL ⚠️
WS_URL = "wss://your-render-url-here.onrender.com" 

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
# 3. SESSION STATE & HELPER FUNCTIONS
# ==========================================
if "q" not in st.session_state: st.session_state.q = queue.Queue()
if "outbox" not in st.session_state: st.session_state.outbox = queue.Queue()
if "state" not in st.session_state: st.session_state.state = None
if "online" not in st.session_state: st.session_state.online = []
if "player_id" not in st.session_state: st.session_state.player_id = None
if "name" not in st.session_state: st.session_state.name = None
if "page" not in st.session_state: st.session_state.page = "landing"
if "ws_started" not in st.session_state: st.session_state.ws_started = False
if "difficulty" not in st.session_state: st.session_state.difficulty = "hard"

def ws_thread(q, outbox):
    async def run():
        try:
            async with websockets.connect(WS_URL) as ws:
                async def sender():
                    loop = asyncio.get_event_loop()
                    while True:
                        msg = await loop.run_in_executor(None, outbox.get)
                        await ws.send(json.dumps(msg))
                asyncio.create_task(sender())
                async for raw in ws: q.put(json.loads(raw))
        except Exception as e: q.put({"type": "error", "msg": str(e)})

def start_ws():
    if not st.session_state.ws_started:
        threading.Thread(target=ws_thread, args=(st.session_state.q, st.session_state.outbox), daemon=True).start()
        st.session_state.ws_started = True

def reset_session():
    st.session_state.q = queue.Queue()
    st.session_state.outbox = queue.Queue()
    st.session_state.state = None
    st.session_state.online = []
    st.session_state.player_id = None
    st.session_state.name = None
    st.session_state.page = "landing"
    st.session_state.ws_started = False

def drain_queue():
    while not st.session_state.q.empty():
        msg = st.session_state.q.get()
        if msg["type"] == "welcome":
            st.session_state.player_id = msg["player_id"]
            st.session_state.name = msg["name"]
        elif msg["type"] == "state":
            st.session_state.state = msg["state"]
            st.session_state.online = msg.get("online", [])
        elif msg["type"] == "error":
            st.error(f"Connection error: {msg['msg']}")

# --- Emoji Functions ---
def send_emoji(emoji_char):
    try:
        supabase.table("emojis").insert({"emoji": emoji_char}).execute()
    except Exception: pass

def get_recent_emojis():
    try:
        now = datetime.datetime.now(datetime.timezone.utc)
        five_secs_ago = now - datetime.timedelta(seconds=5)
        response = supabase.table("emojis").select("*").gte("created_at", five_secs_ago.isoformat()).order("created_at").execute()
        return response.data
    except Exception: return []

# ==========================================
# 4. LANDING PAGE
# ==========================================
@st.fragment(run_every=0.5)
def online_board():
    drain_queue()
    if not st.session_state.online: st.info("No players online right now. You could be the first! 🚀")
    else:
        for p in st.session_state.online:
            is_me = p["id"] == st.session_state.player_id
            st.markdown(f"🟢 **{p['name']}**" + (" *(you)*" if is_me else ""))

@st.dialog("Choose AI difficulty")
def difficulty_dialog():
    choice = st.radio("Difficulty", ["easy", "medium", "hard"], index=["easy", "medium", "hard"].index(st.session_state.difficulty), horizontal=True)
    if st.button("Start AI game", type="primary", use_container_width=True):
        st.session_state.difficulty = choice
        st.session_state.page = "waiting_ai"
        st.session_state.outbox.put({"type": "play_ai", "difficulty": choice})
        st.rerun()

def landing():
    start_ws()
    st.markdown("<div class='hero'><h1>🎮 GRID CLASH</h1><p>Two players. One grid. Infinite swagger.</p></div>", unsafe_allow_html=True)
    st.subheader("👥 Who's online")
    online_board()
    st.divider()
    col1, col2 = st.columns(2)
    with col1:
        if st.button("👥 Wait for a human", use_container_width=True, type="primary"):
            st.session_state.page = "waiting"
            st.rerun()
    with col2:
        if st.button("🤖 Play AI now", use_container_width=True): difficulty_dialog()

# ==========================================
# 5. WAITING PAGE
# ==========================================
@st.fragment(run_every=0.5)
def waiting_fragment():
    drain_queue()
    state = st.session_state.state
    pid = st.session_state.player_id
    if isinstance(state, dict) and "players" in state and pid is not None:
        if pid in state["players"] or state.get("vs_ai"):
            st.session_state.page = "game"
            st.rerun()
            return
    st.markdown("### 🟡 Waiting for an opponent…")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🤖 Play AI instead", use_container_width=True): difficulty_dialog()
    with col2:
        if st.button("🚪 Cancel", use_container_width=True):
            st.session_state.outbox.put({"type": "exit"})
            reset_session()
            st.rerun()

# ==========================================
# 6. THE GAME PAGE (With Emojis!)
# ==========================================
@st.fragment(run_every=0.5)
def game_fragment():
    drain_queue()
    
    # --- RENDER FLOATING EMOJIS ---
    recent_emojis = get_recent_emojis()
    html_output = ""
    for row in recent_emojis:
        emoji = row.get("emoji")
        if emoji:
            left_pos = random.randint(10, 90)
            html_output += f'<div class="floating-emoji" style="left: {left_pos}vw;">{emoji}</div>'
    if html_output:
        st.markdown(html_output, unsafe_allow_html=True)
    # ------------------------------

    state = st.session_state.state
    pid = st.session_state.player_id

    if not isinstance(state, dict) or "players" not in state or pid is None:
        st.info("Connecting…")
        return

    st.markdown(f"**You:** <span class='name-tag'>🧑 {st.session_state.name}</span>", unsafe_allow_html=True)
    my_sym = "X" if state["players"].index(pid) == 0 else "O"

    if state.get("vs_ai"):
        st.info(f"🤖 Playing vs **{state.get('ai_name', 'AI')}** ({state.get('ai_difficulty')})")
    else:
        opp = [p for p in state["players"] if p != pid]
        st.success(f"👥 Playing vs **{state['names'].get(opp[0], '?') if opp else 'waiting...'}**")

    st.write(f"Turn: **{state['turn']}**")
    if state["winner"]: st.success(f"🏆 Winner: **{state['winner']}**")

    # Render the Tic-Tac-Toe Board
    my_turn = (state["turn"] == my_sym and not state["winner"])
    for r in range(3):
        cols = st.columns(3)
        for c in range(3):
            cell = state["board"][r][c]
            if cols[c].button("·" if cell == "." else cell, key=f"c{r}{c}", use_container_width=True, disabled=not my_turn or cell != "."):
                st.session_state.outbox.put({"type": "move", "row": r, "col": c})

    st.divider()
    
    # Emoji Buttons inside the game
    st.write("**Send a reaction:**")
    e1, e2, e3, e4 = st.columns(4)
    if e1.button("🔥", use_container_width=True): send_emoji("🔥")
    if e2.button("❤️", use_container_width=True): send_emoji("❤️")
    if e3.button("😂", use_container_width=True): send_emoji("😂")
    if e4.button("🚀", use_container_width=True): send_emoji("🚀")

    st.divider()
    if st.button("🚪 Exit Game", use_container_width=True):
        st.session_state.outbox.put({"type": "exit"})
        reset_session()
        st.rerun()

# ==========================================
# 7. ROUTER
# ==========================================
page = st.session_state.page
if page == "landing": landing()
elif page in ("waiting", "waiting_ai"): waiting_fragment()
elif page == "game": game_fragment()
