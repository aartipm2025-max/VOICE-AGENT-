import streamlit as st
import asyncio
import os
import sys
import uuid
import requests
import speech_recognition as sr
import edge_tts
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Optional, List

# --- Core App Logic (Direct Integration) ---
from core.session import get_session, create_session as create_session_core, delete_session, State
from core.handler import handle

# Set page config
st.set_page_config(
    page_title="Advisor Voice Agent",
    page_icon="🎙️",
    layout="centered"
)

# Custom CSS
st.markdown("""
<style>
    .stApp {
        background: #ffffff !important;
    }
    .stMarkdown, .stText, p, h1, h2, h3, h4, h5, h6, span, label {
        color: #000000 !important;
    }
    .glass-card {
        background: rgba(0, 0, 0, 0.05);
        border: 1px solid rgba(0, 0, 0, 0.1);
        border-radius: 20px;
        padding: 2rem;
        margin-bottom: 1rem;
    }
    .header-text {
        font-weight: 800;
        font-size: 2.5rem;
        color: #000000 !important;
        text-align: center;
        margin-bottom: 0;
    }
    /* Ensure chat messages are visible in light mode */
    [data-testid="stChatMessage"] {
        background-color: #f0f2f6 !important;
        border: 1px solid #e0e0e0 !important;
    }
    [data-testid="stChatMessage"] p {
        color: #000000 !important;
    }
</style>
""", unsafe_allow_html=True)

# Helper: TTS
async def generate_speech(text: str) -> str:
    voice = "en-IN-NeerjaNeural"
    filename = f"resp_{uuid.uuid4().hex}.mp3"
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(filename)
    return filename

# Session Management
if 'session_id' not in st.session_state:
    st.session_state.session_id = None
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []
if 'audio_to_play' not in st.session_state:
    st.session_state.audio_to_play = None

def start_new_session():
    # Clear old audio files if they exist
    for f in os.listdir("."):
        if f.startswith("resp_") and f.endswith(".mp3"):
            try: os.remove(f)
            except: pass
            
    session = create_session_core()
    st.session_state.session_id = session.session_id
    # Initial greeting
    responses = handle("", session)
    greeting = " ".join(responses)
    st.session_state.chat_history = [{"role": "assistant", "content": greeting}]
    st.session_state.audio_to_play = asyncio.run(generate_speech(greeting))

# UI Header
st.markdown("<h1 class='header-text'>Advisor Voice Agent</h1>", unsafe_allow_html=True)
st.write("<p style='text-align:center; color:#cbd5e1;'>Complete Hands-Free Scheduling</p>", unsafe_allow_html=True)

# Start/Reset Session
if not st.session_state.session_id:
    if st.button("🚀 Connect to Advisor Agent", use_container_width=True):
        start_new_session()
        st.rerun()
else:
    # Chat Window
    for chat in st.session_state.chat_history:
        with st.chat_message(chat["role"]):
            st.write(chat["content"])

    # Auto-play audio if ready
    if st.session_state.audio_to_play:
        st.audio(st.session_state.audio_to_play, format="audio/mp3", autoplay=True)
        st.session_state.audio_to_play = None

    # Input: Microphone
    audio_value = st.audio_input("Tap to speak to the Advisor")
    
    if audio_value:
        recognizer = sr.Recognizer()
        try:
            with sr.AudioFile(audio_value) as source:
                audio_data = recognizer.record(source)
                user_text = recognizer.recognize_google(audio_data, language="en-IN")
                
                if user_text:
                    st.session_state.chat_history.append({"role": "user", "content": user_text})
                    
                    # Process with core handler
                    session = get_session(st.session_state.session_id)
                    if session:
                        responses = handle(user_text, session)
                        assistant_text = " ".join(responses)
                        st.session_state.chat_history.append({"role": "assistant", "content": assistant_text})
                        st.session_state.audio_to_play = asyncio.run(generate_speech(assistant_text))
                        st.rerun()
        except Exception as e:
            st.error(f"Error: {e}")

    # Sidebar Tools
    with st.sidebar:
        st.title("Settings")
        if st.button("Reset Session"):
            st.session_state.session_id = None
            st.session_state.chat_history = []
            st.rerun()
        
        session = get_session(st.session_state.session_id) if st.session_state.session_id else None
        if session:
            st.write("---")
            st.write(f"**Session ID:** `{session.session_id[:8]}...` ")
            st.write(f"**State:** `{session.state.name}`")
            if session.topic: st.write(f"**Topic:** `{session.topic.value}`")
            if session.booking_code: st.write(f"**Booking Code:** :green[{session.booking_code}]")
