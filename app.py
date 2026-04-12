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
from core.session import get_session, create_session as create_session_core, delete_session, State, Topic
from core.handler import handle

# Set page config
st.set_page_config(
    page_title="Advisor Voice Agent",
    page_icon="🎙️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for Premium Design
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Outfit', sans-serif;
    }
    
    .stApp {
        background: radial-gradient(circle at top right, #f8fafc, #eff6ff);
    }
    
    /* Progress Bar Styles */
    .step-container {
        display: flex;
        justify-content: space-between;
        margin-bottom: 2rem;
        padding: 0 1rem;
    }
    .step {
        text-align: center;
        flex: 1;
        position: relative;
    }
    .step-circle {
        width: 35px;
        height: 35px;
        border-radius: 50%;
        background: #e2e8f0;
        margin: 0 auto 5px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: 600;
        color: #64748b;
        border: 3px solid #fff;
        box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);
        transition: all 0.3s ease;
    }
    .step.active .step-circle {
        background: #2563eb;
        color: white;
        transform: scale(1.1);
    }
    .step.completed .step-circle {
        background: #10b981;
        color: white;
    }
    .step-label {
        font-size: 0.75rem;
        color: #64748b;
        font-weight: 500;
    }
    .step.active .step-label {
        color: #1e3a8a;
        font-weight: 700;
    }
    
    /* Chat bubbles */
    [data-testid="stChatMessage"] {
        border-radius: 20px !important;
        padding: 1rem !important;
        margin-bottom: 0.8rem !important;
        border: 1px solid rgba(0,0,0,0.05) !important;
        box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05) !important;
    }
    
    .stChatMessage.assistant {
        background-color: #ffffff !important;
    }
    
    .stChatMessage.user {
        background-color: #dbeafe !important;
        border-color: #bfdbfe !important;
    }

    /* Success Card */
    .success-card {
        background: linear-gradient(135deg, #1e3a8a 0%, #3b82f6 100%);
        color: white !important;
        border-radius: 24px;
        padding: 2.5rem;
        text-align: center;
        box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04);
        margin: 2rem 0;
    }
    .booking-code {
        font-family: 'Courier New', Courier, monospace;
        font-size: 3rem;
        font-weight: 800;
        letter-spacing: 5px;
        margin: 1rem 0;
        background: rgba(255,255,255,0.2);
        padding: 1rem;
        border-radius: 12px;
        display: inline-block;
    }
    
    /* IST Badge */
    .ist-badge {
        background: #f1f5f9;
        color: #475569;
        font-weight: 600;
        font-size: 0.7rem;
        padding: 4px 10px;
        border-radius: 100px;
        display: inline-flex;
        align-items: center;
        gap: 5px;
        border: 1px solid #e2e8f0;
    }
    
    .disclaimer-bar {
        background: #fffbeb;
        border: 1px solid #fde68a;
        color: #92400e;
        padding: 10px;
        border-radius: 10px;
        font-size: 0.85rem;
        margin-bottom: 1.5rem;
        text-align: center;
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
    # Clear old audio files
    for f in os.listdir("."):
        if f.startswith("resp_") and f.endswith(".mp3"):
            try: os.remove(f)
            except: pass
            
    session = create_session_core()
    st.session_state.session_id = session.session_id
    responses = handle("", session)
    greeting = " ".join(responses)
    st.session_state.chat_history = [{"role": "assistant", "content": greeting}]
    # Run TTS async in the event loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    st.session_state.audio_to_play = loop.run_until_complete(generate_speech(greeting))

# Mapping States to Steps
STEPS = [
    ("Intro", [State.GREETING, State.AWAIT_INTENT]),
    ("Topic", [State.COLLECT_TOPIC]),
    ("Time", [State.COLLECT_TIME_PREF, State.OFFER_SLOTS]),
    ("Confirm", [State.CONFIRM_BOOKING]),
    ("Sync", [State.MCP_SIDE_EFFECTS, State.HANDOFF]),
    ("Done", [State.ENDED])
]

# UI LAYOUT
col_main, col_side = st.columns([2.5, 1])

with col_main:
    # Header & IST Badge
    st.markdown("""
        <div style="display:flex; justify-content:space-between; align-items:center;">
            <h1 style="margin-bottom:0; font-weight:800; color:#1e293b;">Advisor Voice Agent</h1>
            <div class="ist-badge">
                <span style="color:#10b981;">●</span> LIVE IN IST (UTC+5:30)
            </div>
        </div>
        <p style="color:#64748b; font-size:1.1rem; margin-top:0.2rem;">Complete Hands-Free Consultation Scheduling</p>
    """, unsafe_allow_html=True)

    # Progress Tracker
    session = get_session(st.session_state.session_id) if st.session_state.session_id else None
    curr_state = session.state if session else State.GREETING
    
    cols = st.columns(len(STEPS))
    for i, (label, states) in enumerate(STEPS):
        is_active = curr_state in states
        is_completed = any(curr_state in s for l, s in STEPS[i+1:]) if i < len(STEPS)-1 else False
        status_class = "active" if is_active else ("completed" if is_completed else "")
        
        with cols[i]:
            st.markdown(f"""
                <div class="step {status_class}">
                    <div class="step-circle">{'✓' if is_completed else i+1}</div>
                    <div class="step-label">{label}</div>
                </div>
            """, unsafe_allow_html=True)

    st.write("---")

    # Disclaimer
    st.markdown("""
        <div class="disclaimer-bar">
            ⚠️ <b>Note:</b> This agent provides informational scheduling only and NOT investment advice.
        </div>
    """, unsafe_allow_html=True)

    if not st.session_state.session_id:
        st.info("👋 Hello! Welcome to the Advisor Scheduler. Click below to start your hands-free booking session.")
        if st.button("🚀 Connect to Advisor Agent", use_container_width=True, type="primary"):
            start_new_session()
            st.rerun()
    else:
        # Check if conversation ended
        if session.state == State.ENDED and session.booking_code:
            st.markdown(f"""
                <div class="success-card">
                    <div style="font-size:3rem; margin-bottom:1rem;">🎯</div>
                    <h2 style="color:white; margin:0; font-weight:800;">BOOKING CONFIRMED!</h2>
                    <p style="opacity:0.9; margin-bottom:2rem;">Your tentative slot is reserved in the Advisor's calendar.</p>
                    <div class="booking-code">{session.booking_code}</div>
                    <p style="margin-top:1rem; font-weight:600;">SAVE THIS CODE</p>
                    <div style="margin-top:2rem;">
                        <a href="https://secure.app/{session.booking_code}" target="_blank" 
                           style="background:white; color:#2563eb; padding:12px 30px; border-radius:12px; 
                           text-decoration:none; font-weight:800; display:inline-block; box-shadow:0 10px 15px -3px rgba(0,0,0,0.1);">
                           FINISH SECURE SETUP →
                        </a>
                    </div>
                </div>
            """, unsafe_allow_html=True)
            st.success(f"Tentative appointment for **{session.topic.value if session.topic else 'Consultation'}** is set. Goodbye!")
        else:
            # Chat Window
            chat_container = st.container()
            with chat_container:
                for chat in st.session_state.chat_history:
                    with st.chat_message(chat["role"]):
                        st.write(chat["content"])

            # Auto-play audio
            if st.session_state.audio_to_play:
                st.audio(st.session_state.audio_to_play, format="audio/mp3", autoplay=True)
                st.session_state.audio_to_play = None

            # Input area spacer
            st.write("")
            
            # Contextual UI elements (Topic Selection)
            if session.state == State.COLLECT_TOPIC:
                st.markdown("##### 📍 Select a Topic")
                t_cols = st.columns(3)
                topics = list(Topic)
                for i, t in enumerate(topics):
                    with t_cols[i % 3]:
                        if st.button(t.value, key=f"t_{i}", use_container_width=True):
                            # Simulate voice input of topic name
                            user_text = t.value
                            st.session_state.chat_history.append({"role": "user", "content": user_text})
                            responses = handle(user_text, session)
                            assistant_text = " ".join(responses)
                            st.session_state.chat_history.append({"role": "assistant", "content": assistant_text})
                            loop = asyncio.new_event_loop()
                            st.session_state.audio_to_play = loop.run_until_complete(generate_speech(assistant_text))
                            st.rerun()

            # Voice Input
            audio_value = st.audio_input("Tap to speak to the Advisor")
            
            if audio_value:
                recognizer = sr.Recognizer()
                try:
                    with sr.AudioFile(audio_value) as source:
                        audio_data = recognizer.record(source)
                        user_text = recognizer.recognize_google(audio_data, language="en-IN")
                        
                        if user_text:
                            st.session_state.chat_history.append({"role": "user", "content": user_text})
                            responses = handle(user_text, session)
                            assistant_text = " ".join(responses)
                            st.session_state.chat_history.append({"role": "assistant", "content": assistant_text})
                            # Run TTS
                            loop = asyncio.new_event_loop()
                            st.session_state.audio_to_play = loop.run_until_complete(generate_speech(assistant_text))
                            st.rerun()
                except sr.UnknownValueError:
                    st.warning("I couldn't understand the audio. Please try speaking more clearly or typing if needed.")
                except sr.RequestError as e:
                    st.error(f"Speech service error: {e}")
                except Exception as e:
                    st.error(f"Error: {e}")

# SIDEBAR
with col_side:
    st.markdown("""
        <div style="background:white; padding:1.5rem; border-radius:20px; border:1px solid #e2e8f0; box-shadow:0 4px 6px -1px rgba(0,0,0,0.05);">
            <h3 style="margin-top:0; color:#1e293b;">Session Console</h3>
    """, unsafe_allow_html=True)
    
    if session:
        st.write(f"**Status:** :blue[{session.state.name}]")
        if session.topic: 
            st.write(f"**Topic:** `{session.topic.value}`")
            
            # Contextual Preparation Sidebar logic
            st.write("---")
            st.markdown("##### 📋 What to Prepare")
            prep_tips = {
                Topic.KYC_ONBOARDING: ["Aadhaar/PAN Card", "Cancel Cheque", "Address Proof"],
                Topic.SIP_MANDATES: ["Bank Account Details", "Mobile linked with Bank", "Mandate Limit"],
                Topic.STATEMENTS_TAX_DOCS: ["Previous Year IT Returns", "Bank Statements", "Login Credentials"],
                Topic.WITHDRAWALS_TIMELINES: ["Folio Numbers", "Redemption Forms", "Bank link confirmation"],
                Topic.ACCOUNT_CHANGES_NOMINEE: ["Nominee ID Proof", "Relationship Proof", "Witness details"]
            }
            tips = prep_tips.get(session.topic, ["Valid ID Proof", "Recent Statements", "List of Questions"])
            for tip in tips:
                st.markdown(f"- {tip}")
        
    st.write("---")
    if st.button("🔄 Reset Session", use_container_width=True):
        st.session_state.session_id = None
        st.session_state.chat_history = []
        st.rerun()
    
    st.markdown("</div>", unsafe_allow_html=True)
    
    st.write("")
    with st.expander("Technical Overview"):
        st.caption("FSM-based conversation manager with Google Voice/Gemini fallback logic.")
        if session:
            st.json({
                "session_id": session.session_id,
                "state": session.state.name,
                "offered_slots": len(session.offered_slots)
            })

# Footer
st.markdown("""
    <div style="text-align:center; color:#94a3b8; font-size:0.8rem; margin-top:3rem;">
        Compliant Voice Agent v1.2 | No Personal Data Collected | Powered by Gemini 2.0
    </div>
""", unsafe_allow_html=True)
