# app.py
import asyncio, json, queue, threading
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
    """Pull all pending WS messages into session state."""
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
        if len(online) == 1:
            st.caption("Waiting for a second player…")
        else:
            st.caption("Ready to play — someone else is here!")

def landing():
    # Connect immediately so online list is live even before clicking Play
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
            st.session_state.page = "waiting_ai"
            st.session_state.outbox.put({"type": "set_mode", "mode": "ai_now"})
            st.rerun()

    with st.expander("ℹ️ How it works"):
        st.write("""
        - You get a random codename when you enter.
        - **Wait for a human**: if someone joins within 3s → human match. Otherwise AI steps in.
        - **Play AI now**: skips waiting and goes straight to a bot match.
        - Hit **Exit** any time to leave.
        """)

# ---------- WAITING ----------
@st.fragment(run_every=0.5)
def waiting_fragment():
    drain_queue()

    state = st.session_state.state
    pid = st.session_state.player_id

    if not isinstance(state, dict) or "players" not in state or pid is None:
        st.info("Connecting…")
        return

    if pid in state["players"] or state.get("vs_ai"):
        st.session_state.page = "game"
        st.rerun()
        return

    st.markdown("### 🟡 Waiting for an opponent…")
    st.write(f"You are **{st.session_state.name}**")
    online = st.session_state.online
    st.write(f"Players online: **{len(online)}**")
    for p in online:
        st.markdown(f"- 🟢 {p['name']}")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("🤖 Play AI instead", use_container_width=True):
            st.session_state.outbox.put({"type": "play_ai"})
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

    st.markdown(
        f"**You:** <span class='name-tag'>🧑 {st.session_state.name or '…'}</span>",
        unsafe_allow_html=True,
    )

    if pid not in state["players"]:
        st.warning("Game full — try another tab.")
        if st.button("⬅️ Back to lobby"):
            reset_session()
            st.rerun()
        return

    my_sym = "X" if state["players"].index(pid) == 0 else "O"

    if state.get("vs_ai"):
        st.info(f"🤖 No human found — playing vs **{state.get('ai_name', 'AI')}** (O)")
    else:
        opp_ids = [p for p in state["players"] if p != pid]
        opp_name = state["names"].get(opp_ids[0], "?") if opp_ids else "waiting…"
        st.success(f"👥 Playing vs **{opp_name}** (human)")

    st.write(f"You are **{my_sym}** · turn: **{state['turn']}**")
    if state["winner"]:
        if state["winner"] == "draw":
            st.warning("It's a draw!")
        else:
            st.success(f"🏆 Winner: **{state['winner']}**")

    my_turn = (state["turn"] == my_sym and not state["winner"])
    for r in range(3):
        cols = st.columns(3)
        for c in range(3):
            cell = state["board"][r][c]
            label = "·" if cell == "." else cell
            if cols[c].button(label, key=f"c{r}{c}", use_container_width=True,
                              disabled=not my_turn or cell != "."):
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
