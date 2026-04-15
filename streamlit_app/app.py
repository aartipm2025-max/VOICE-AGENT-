import streamlit as st
import os
import sys
import requests

# Add parent directory to path to import core logic if needed directly
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set page config for a premium look
st.set_page_config(
    page_title="Advisor Chat Agent",
    page_icon="💬",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# API Configuration
API_URL = "http://127.0.0.1:8000"

# Custom CSS for Glassmorphism & Aesthetics
st.markdown("""
<style>
    .stApp {
        background: #ffffff;
        color: #000000;
    }
    .glass-card {
        background: #ffffff;
        border: 1px solid #000000;
        border-radius: 20px;
        padding: 2rem;
        margin-bottom: 1rem;
    }
    .header-text {
        font-weight: 800;
        font-size: 2.5rem;
        color: #000000;
        text-align: center;
        margin-bottom: 0;
    }
    .sub-text {
        color: #000000;
        text-align: center;
        font-size: 1.1rem;
        margin-bottom: 2rem;
    }
    div[data-testid="stChatMessage"] {
        border: 1px solid #000000;
        background: #f3f4f6;
        color: #000000;
    }
    .stChatInputContainer {
        border: 1px solid #000000 !important;
        background: #ffffff !important;
    }
    .stButton > button {
        background: #000000 !important;
        color: #ffffff !important;
        border: 1px solid #000000 !important;
    }
    .stChatInput textarea {
        color: #000000 !important;
        background: #ffffff !important;
    }
    /* Hide Streamlit elements for cleaner look */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'session_id' not in st.session_state:
    st.session_state.session_id = None
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []

def init_backend_session():
    try:
        res = requests.post(f"{API_URL}/session")
        if res.status_code != 200:
            st.error(f"Failed to create session: HTTP {res.status_code}")
            return

        data = res.json()
        st.session_state.session_id = data["session_id"]

        # Get initial greeting
        msg_res = requests.post(
            f"{API_URL}/message",
            json={"session_id": st.session_state.session_id, "text": ""},
        )
        if msg_res.status_code != 200:
            st.error(f"Failed to fetch greeting: HTTP {msg_res.status_code}")
            return

        responses = msg_res.json().get("responses", [])
        greeting = " ".join(responses).strip()
        if greeting:
            st.session_state.chat_history.append({"role": "assistant", "content": greeting})
    except Exception as e:
        st.error(f"Backend connection failed. Is the API server running? {e}")

# Header
st.markdown("<h1 class='header-text'>Advisor Chat Agent</h1>", unsafe_allow_html=True)
st.markdown("<p class='sub-text'>Compliant appointment scheduling over chat.</p>", unsafe_allow_html=True)

# Main Container
with st.container():
    if not st.session_state.session_id:
        if st.button("🚀 Start Conversation", use_container_width=True):
            init_backend_session()
            st.rerun()
    else:
        # Chat display
        for chat in st.session_state.chat_history:
            with st.chat_message(chat["role"]):
                st.write(chat["content"])

        user_text = st.chat_input("Type your message")
        if user_text:
            st.session_state.chat_history.append({"role": "user", "content": user_text})
            try:
                res = requests.post(
                    f"{API_URL}/message",
                    json={"session_id": st.session_state.session_id, "text": user_text},
                )
                if res.status_code != 200:
                    st.error(f"Backend returned HTTP {res.status_code}")
                    st.stop()
                data = res.json()
                assistant_text = " ".join(data.get("responses", []))
                if assistant_text:
                    st.session_state.chat_history.append({"role": "assistant", "content": assistant_text})
                st.rerun()
            except Exception as e:
                st.error(f"Processing error: {e}")

        # Reset button
        if st.button("Clear Session", type="secondary"):
            if st.session_state.session_id:
                try:
                    requests.delete(f"{API_URL}/session/{st.session_state.session_id}")
                except Exception:
                    # Clearing UI state is sufficient even if backend cleanup fails.
                    pass
            st.session_state.session_id = None
            st.session_state.chat_history = []
            st.rerun()
