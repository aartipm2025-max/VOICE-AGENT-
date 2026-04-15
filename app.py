import streamlit as st
import time
from core.session import get_session, create_session as create_session_core, State
from core.handler import handle

st.set_page_config(
    page_title="Advisor Chat Agent",
    page_icon="💼",
    layout="centered"
)

# Custom CSS for premium aesthetics
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }
    .stApp {
        background: linear-gradient(-45deg, #0f172a, #1e1b4b, #312e81, #0f172a);
        background-size: 400% 400%;
        animation: gradientBG 15s ease infinite;
    }
    @keyframes gradientBG {
        0% { background-position: 0% 50%; }
        50% { background-position: 100% 50%; }
        100% { background-position: 0% 50%; }
    }
    .header-style {
        text-align: center;
        background: -webkit-linear-gradient(45deg, #38bdf8, #a78bfa);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 800;
        font-size: 2.8rem;
        padding-bottom: 0;
        margin-bottom: 0;
    }
    .sub-header {
        text-align: center;
        color: #94a3b8;
        font-size: 1.1rem;
        margin-bottom: 2rem;
    }
    div[data-testid="stChatMessage"] {
        border-radius: 14px;
        padding: 8px 16px;
        margin-bottom: 8px;
        border: 1px solid rgba(255, 255, 255, 0.08);
        background: rgba(255, 255, 255, 0.04);
        backdrop-filter: blur(10px);
    }
    .stChatInputContainer {
        border-radius: 14px !important;
    }
    .status-badge {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 600;
        margin-bottom: 1rem;
    }
    .status-active {
        background: rgba(34, 197, 94, 0.15);
        color: #22c55e;
        border: 1px solid rgba(34, 197, 94, 0.3);
    }
    .status-ended {
        background: rgba(239, 68, 68, 0.15);
        color: #ef4444;
        border: 1px solid rgba(239, 68, 68, 0.3);
    }
</style>
""", unsafe_allow_html=True)

st.markdown("<h1 class='header-style'>💼 Advisor Chat Agent</h1>", unsafe_allow_html=True)
st.markdown("<p class='sub-header'>Compliant appointment scheduling — powered by AI.</p>", unsafe_allow_html=True)

# Initialize Session State
if "session_id" not in st.session_state:
    session = create_session_core()
    st.session_state.session_id = session.session_id
    
    # Trigger the greeting
    responses = handle("", session)
    st.session_state.messages = []
    for r in responses:
        st.session_state.messages.append({"role": "assistant", "content": r})

# Session status badge
session = get_session(st.session_state.session_id)
if session:
    state_name = session.state.name
    if session.state == State.BOOKED or session.state == State.ENDED:
        st.markdown(f"<div style='text-align:center'><span class='status-badge status-ended'>Session: {state_name}</span></div>", unsafe_allow_html=True)
    else:
        st.markdown(f"<div style='text-align:center'><span class='status-badge status-active'>Session: {state_name}</span></div>", unsafe_allow_html=True)

# Render existing chat history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

# User Input
if prompt := st.chat_input("Type your message to the advisor..."):
    session = get_session(st.session_state.session_id)
    
    if not session:
        st.error("Session expired. Please refresh the page.")
        st.stop()

    if session.state == State.BOOKED or session.state == State.ENDED:
        st.info("This conversation has concluded. Refresh the page to start a new one.")
        st.stop()

    # Show user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.write(prompt)

    # Get assistant responses
    with st.chat_message("assistant"):
        with st.spinner("Agent is thinking..."):
            responses = handle(prompt, session)
            for reply in responses:
                st.write(reply)
                st.session_state.messages.append({"role": "assistant", "content": reply})

    # Check for session complete
    if session.state == State.BOOKED or session.state == State.ENDED:
        st.success("✅ Conversation complete! Refresh the page to start a new session.")

    st.rerun()
