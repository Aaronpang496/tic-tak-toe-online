# app.py
import asyncio, json, queue, threading, time
import streamlit as st
import websockets

WS_URL = "ws://localhost:8765"

st.set_page_config(page_title="Grid Clash", page_icon="🎮", layout="centered")

# ---------- session ----------
if "q" not in st.session_state:
    st.session_state.q = queue.Queue()
if "outbox" not in st.session_state:
    st.session_state.outbox = queue.Queue()
if "state" not in st.session_state:
    st.session_state.state = None
if "online" not in st.session_state:
    st.session_state.online = []
if "player_id" not in st.session_state:
    st.session_state.player_id = None
if "name" not in st.session_state:
    st.session_state.name = None
if "page" not in st.session_state:
    st.session_state.page = "landing"
if "ws_started" not in st.session_state:
    st.session_state.ws_started = False
if "difficulty" not in st.session_state:
    st.session_state.difficulty = "hard"

# ---------- websocket thread ----------
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
                async for raw in ws:
                    q.put(json.loads(raw))
        except Exception as e:
            q.put({"type": "error", "msg": str(e)})

def start_ws():
    if not st.session_state.ws_started:
        threading.Thread(
            target=ws_thread,
            args=(st.session_state.q, st.session_state.outbox),
            daemon=True,
        ).start()
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

# ---------- CSS ----------
st.markdown("""
<style>
.hero {
  text-align:center; padding: 60px 20px 30px 20px;
  background: linear-gradient(135deg,#6a11cb 0%,#2575fc 100%);
  border-radius: 20px; color: white; margin-bottom: 24px;
}
.hero h1 { font-size: 56px; margin: 0; letter-spacing: 2px; }
.hero p  { font-size: 18px; opacity: 0.9; margin-top: 8px; }
.badge {
  display:inline-block; padding: 4px 12px; border-radius: 999px;
  background: rgba(255,255,255,0.15); font-size: 14px; margin-top: 12px;
}
.name-tag {
  display:inline-block; padding: 6px 14px; border-radius: 999px;
  background: #eef2ff; color: #3730a3; font-weight: 600; margin: 4px 0;
}
.online-row {
  display:flex; align-items:center; gap:8px; padding: 6px 10px;
  border-radius: 8px; background: #f9fafb; margin-bottom: 4px;
}
.dot { width:10px; height:10px; border-radius:50%; background:#22c55e; }
</style>
""", unsafe_allow_html=True)

# ---------- LANDING ----------
@st.fragment(run_every=0.5)
def online_board():
    drain_queue()
    online = st.session_state.online
    if not online:
        st.info("No players online right now. You could be the first! 🚀")
    else:
        for p in online:
            is_me = p["id"] == st.session_state.player_id
            label = f"🟢 **{p['name']}**" + (" *(you)*" if is_me else "")
            st.markdown(f"<div class='online-row'>{label}</div>", unsafe_allow_html=True)

@st.dialog("Choose AI difficulty")
def difficulty_dialog():
    st.write("How tough should the bot be?")
    choice = st.radio(
        "Difficulty",
        options=["easy", "medium", "hard"],
        index=["easy", "medium", "hard"].index(st.session_state.difficulty),
        horizontal=True,
        label_visibility="collapsed",
    )
    st.caption({"easy": "🎲 Random moves.", "medium": "🤔 50% optimal.", "hard": "🧠 Perfect play."}[choice])

    if st.button("Start AI game", type="primary", use_container_width=True):
        st.session_state.difficulty = choice
        st.session_state.page = "waiting_ai"
        st.session_state.outbox.put({"type": "play_ai", "difficulty": choice})
        st.rerun()

def landing():
    start_ws()
    st.markdown("""
    <div class="hero">
      <h1>🎮 GRID CLASH</h1>
      <p>Two players. One grid. Infinite swagger.</p>
      <div class="badge">🟣 Play a human if one shows up · otherwise a friendly AI</div>
    </div>
    """, unsafe_allow_html=True)
    st.subheader("👥 Who's online")
    online_board()
    st.divider()
    col1, col2 = st.columns(2)
    with col1:
        if st.button("👥 Wait for a human", use_container_width=True, type="primary"):
            st.session_state.page = "waiting"
            st.session_state.outbox.put({"type": "set_mode", "mode": "auto"})
            st.rerun()
    with col2:
        if st.button("🤖 Play AI now", use_container_width=True):
            difficulty_dialog()
    with st.expander("ℹ️ How it works"):
        st.write("Pick a mode. If you wait and no one joins, the AI takes over.")

# ---------- WAITING ----------
@st.fragment(run_every=0.5)
def waiting_fragment():
    drain_queue()
    state = st.session_state.state
    pid = st.session_state.player_id

    # Jump to game if ready
    if isinstance(state, dict) and "players" in state and pid is not None:
        if pid in state["players"] or state.get("vs_ai"):
            st.session_state.page = "game"
            st.rerun()
            return

    if not isinstance(state, dict) or "players" not in state or pid is None:
        st.info("Connecting…")
        return

    st.markdown("### 🟡 Waiting for an opponent…")
    st.write(f"You are **{st.session_state.name}**")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🤖 Play AI instead", use_container_width=True):
            difficulty_dialog()
    with col2:
        if st.button("🚪 Cancel", use_container_width=True):
            st.session_state.outbox.put({"type": "exit"})
            reset_session()
            st.rerun()

# ---------- GAME ----------
@st.fragment(run_every=0.5)
def game_fragment():
    drain_queue()
    state = st.session_state.state
    pid = st.session_state.player_id

    if not isinstance(state, dict) or "players" not in state or pid is None:
        st.info("Connecting…")
        return

    if pid not in state["players"]:
        st.warning("Game full or you left.")
        if st.button("⬅️ Back"):
            reset_session()
            st.rerun()
        return

    st.markdown(f"**You:** <span class='name-tag'>🧑 {st.session_state.name}</span>", unsafe_allow_html=True)
    my_sym = "X" if state["players"].index(pid) == 0 else "O"

    if state.get("vs_ai"):
        diff = state.get("ai_difficulty", "hard")
        emoji = {"easy": "🎲", "medium": "🤔", "hard": "🧠"}[diff]
        st.info(f"{emoji} Playing vs **{state.get('ai_name', 'AI')}** (O) · {diff}")
    else:
        opp = [p for p in state["players"] if p != pid]
        opp_name = state["names"].get(opp[0], "?") if opp else "waiting…"
        st.success(f"👥 Playing vs **{opp_name}**")

    st.write(f"Turn: **{state['turn']}**")
    if state["winner"]:
        st.success(f"🏆 Winner: **{state['winner']}**") if state["winner"] != "draw" else st.warning("Draw!")

    my_turn = (state["turn"] == my_sym and not state["winner"])
    for r in range(3):
        cols = st.columns(3)
        for c in range(3):
            cell = state["board"][r][c]
            label = "·" if cell == "." else cell
            if cols[c].button(label, key=f"c{r}{c}", use_container_width=True, disabled=not my_turn or cell != "."):
                st.session_state.outbox.put({"type": "move", "row": r, "col": c})

    st.divider()
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔄 Reset", use_container_width=True):
            st.session_state.outbox.put({"type": "reset"})
    with col2:
        if st.button("🚪 Exit", use_container_width=True):
            st.session_state.outbox.put({"type": "exit"})
            reset_session()
            st.rerun()

# ---------- ROUTER ----------
page = st.session_state.page
if page == "landing":
    landing()
elif page in ("waiting", "waiting_ai"):
    waiting_fragment()
elif page == "game":
    game_fragment()
