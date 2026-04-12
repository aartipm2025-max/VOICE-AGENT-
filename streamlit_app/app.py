import streamlit as st
import asyncio
import os
import sys
import uuid
import requests
import speech_recognition as sr
import edge_tts
from dataclasses import dataclass
from typing import List

# Add parent directory to path to import core logic if needed directly
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set page config for a premium look
st.set_page_config(
    page_title="Advisor Voice Agent",
    page_icon="🎙️",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# API Configuration
API_URL = "http://127.0.0.1:8000"

# Custom CSS for Glassmorphism & Aesthetics
st.markdown("""
<style>
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
    .glass-card {
        background: rgba(255, 255, 255, 0.05);
        backdrop-filter: blur(16px);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 20px;
        padding: 2rem;
        margin-bottom: 1rem;
    }
    .header-text {
        font-weight: 800;
        font-size: 2.5rem;
        background: -webkit-linear-gradient(45deg, #38bdf8, #a78bfa);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-align: center;
        margin-bottom: 0;
    }
    .sub-text {
        color: #cbd5e1;
        text-align: center;
        font-size: 1.1rem;
        margin-bottom: 2rem;
    }
    /* Hide Streamlit elements for cleaner look */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# Helper: Text to Speech
async def generate_speech(text: str) -> str:
    voice = "en-IN-NeerjaNeural"
    filename = f"resp_{uuid.uuid4().hex}.mp3"
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(filename)
    return filename

# Initialize session state
if 'session_id' not in st.session_state:
    st.session_state.session_id = None
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []
if 'audio_to_play' not in st.session_state:
    st.session_state.audio_to_play = None

def init_backend_session():
    try:
        res = requests.post(f"{API_URL}/session")
        if res.status_code == 200:
            data = res.json()
            st.session_state.session_id = data["session_id"]
            # Get initial greeting
            msg_res = requests.post(f"{API_URL}/message", json={"session_id": st.session_state.session_id, "text": ""})
            responses = msg_res.json().get("responses", [])
            greeting = " ".join(responses)
            st.session_state.chat_history.append({"role": "assistant", "content": greeting})
            # Generate audio for greeting
            st.session_state.audio_to_play = asyncio.run(generate_speech(greeting))
    except Exception as e:
        st.error(f"Backend connection failed. Is the API server running? {e}")

# Header
st.markdown("<h1 class='header-text'>Advisor Voice Agent</h1>", unsafe_allow_html=True)
st.markdown("<p class='sub-text'>Hands-free compliant appointment scheduling.</p>", unsafe_allow_html=True)

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

        # Audio Output (Hidden auto-play)
        if st.session_state.audio_to_play:
            st.audio(st.session_state.audio_to_play, format="audio/mp3", autoplay=True)
            st.session_state.audio_to_play = None

        # Voice Input Component
        st.write("---")
        audio_value = st.audio_input("Speak to the Agent")
        
        if audio_value:
            # 1. Transcribe
            recognizer = sr.Recognizer()
            try:
                with sr.AudioFile(audio_value) as source:
                    audio_data = recognizer.record(source)
                    user_text = recognizer.recognize_google(audio_data, language="en-IN")
                    
                    if user_text:
                        st.session_state.chat_history.append({"role": "user", "content": user_text})
                        
                        # 2. Call backend
                        res = requests.post(f"{API_URL}/message", json={
                            "session_id": st.session_state.session_id,
                            "text": user_text
                        })
                        data = res.json()
                        assistant_text = " ".join(data["responses"])
                        st.session_state.chat_history.append({"role": "assistant", "content": assistant_text})
                        
                        # 3. Speak
                        st.session_state.audio_to_play = asyncio.run(generate_speech(assistant_text))
                        st.rerun()
                        
            except Exception as e:
                st.error(f"Processing error: {e}")

        # Reset button
        if st.button("Clear Session", type="secondary"):
            st.session_state.session_id = None
            st.session_state.chat_history = []
            st.rerun()
