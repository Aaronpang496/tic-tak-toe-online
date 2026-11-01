import streamlit as st
from supabase import create_client, Client
import time
import random
import datetime

# --- 1. SUPABASE SETUP (YOUR CREDENTIALS) ---
SUPABASE_URL = "https://gxdpjxpzyivzlvwyfaoj.supabase.co"
SUPABASE_KEY = "sb_publishable_TQWFXwkHlR90wtnp50z0Dg_zGHKpo5g"

@st.cache_resource
def init_supabase() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase = init_supabase()

st.set_page_config(page_title="Online Emoji Float", page_icon="✨", layout="centered")

# --- 2. CSS FOR ANIMATION ---
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
</style>
""", unsafe_allow_html=True)

# --- 3. HELPER FUNCTIONS ---
def send_emoji(emoji_char):
    """Insert a new emoji into the Supabase database."""
    try:
        supabase.table("emojis").insert({"emoji": emoji_char}).execute()
    except Exception as e:
        st.error(f"Failed to send: {e}")

def get_recent_emojis():
    """Fetch emojis created in the last 5 seconds."""
    try:
        # Get current UTC time and 5 seconds ago
        now = datetime.datetime.now(datetime.timezone.utc)
        five_secs_ago = now - datetime.timedelta(seconds=5)
        
        # Format for Supabase
        iso_time = five_secs_ago.isoformat()
        
        response = supabase.table("emojis").select("*").gte("created_at", iso_time).order("created_at").execute()
        return response.data
    except Exception:
        return []

# --- 4. UI & LOGIC ---
st.title("✨ Online Emoji Board")
st.write("Click a button to send a floating emoji to **everyone** connected right now!")

# Create 4 columns for the buttons
col1, col2, col3, col4 = st.columns(4)

with col1:
    if st.button("🔥 Fire", use_container_width=True):
        send_emoji("🔥")
with col2:
    if st.button("❤️ Heart", use_container_width=True):
        send_emoji("❤️")
with col3:
    if st.button("😂 Laugh", use_container_width=True):
        send_emoji("😂")
with col4:
    if st.button("🚀 Rocket", use_container_width=True):
        send_emoji("🚀")

st.divider()

# --- 5. AUTO-REFRESHING FRAGMENT ---
@st.fragment(run_every=1.0)
def live_emoji_display():
    recent_emojis = get_recent_emojis()
    
    html_output = ""
    for row in recent_emojis:
        emoji = row.get("emoji")
        if emoji:
            left_pos = random.randint(10, 90)
            html_output += f'<div class="floating-emoji" style="left: {left_pos}vw;">{emoji}</div>'
            
    if html_output:
        st.markdown(html_output, unsafe_allow_html=True)
    else:
        st.caption("Waiting for emojis... (Send one!)")

live_emoji_display()
