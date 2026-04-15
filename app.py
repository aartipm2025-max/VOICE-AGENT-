import streamlit as st
import re
from core.session import get_session, create_session as create_session_core, State
from core.handler import handle
from mcp.email_tool import send_client_confirmation_email

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
        background: #ffffff;
        color: #000000;
    }
    .header-style {
        text-align: center;
        color: #000000;
        font-weight: 800;
        font-size: 2.8rem;
        padding-bottom: 0;
        margin-bottom: 0;
    }
    .sub-header {
        text-align: center;
        color: #000000;
        font-size: 1.1rem;
        margin-bottom: 2rem;
    }
    div[data-testid="stChatMessage"] {
        border-radius: 14px;
        padding: 8px 16px;
        margin-bottom: 8px;
        border: 1px solid #000000;
        background: #f3f4f6;
        color: #000000;
    }
    .stChatInputContainer {
        border-radius: 14px !important;
        border: 1px solid #000000 !important;
        background: #ffffff !important;
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
        background: #ffffff;
        color: #000000;
        border: 1px solid #000000;
    }
    .status-ended {
        background: #000000;
        color: #ffffff;
        border: 1px solid #000000;
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


def _is_valid_email(value: str) -> bool:
    return bool(re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value.strip()))

# User Input
if prompt := st.chat_input("Type your message to the advisor..."):
    session = get_session(st.session_state.session_id)
    
    if not session:
        st.error("Session expired. Please refresh the page.")
        st.stop()

    if session.state == State.ENDED:
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

# Post-booking email capture flow
session = get_session(st.session_state.session_id)
if session and session.state == State.BOOKED:
    st.markdown("---")
    st.subheader("Receive booking confirmation by email")

    if session.booking_code and session.chosen_slot and session.topic:
        st.write(
            f"Booking Details: `{session.booking_code}` | `{session.topic.value}` | "
            f"`{session.chosen_slot.date}` at `{session.chosen_slot.time} IST`"
        )

    default_email = session.confirmation_email or ""
    email_input = st.text_input(
        "Enter your email",
        value=default_email,
        placeholder="name@example.com",
        key="booking_email_input",
    )

    if st.button("Send Confirmation Email", use_container_width=True):
        if not _is_valid_email(email_input):
            st.error("Please enter a valid email address.")
        elif not (session.booking_code and session.chosen_slot and session.topic):
            st.error("Booking details are incomplete. Please restart the session.")
        else:
            send_result = send_client_confirmation_email(
                to_email=email_input.strip(),
                topic=session.topic.value,
                code=session.booking_code,
                date=session.chosen_slot.date,
                time=session.chosen_slot.time,
            )
            if send_result.success:
                session.confirmation_email = email_input.strip()
                session.email_sent = True
                confirmation_msg = (
                    f"Confirmation sent to {session.confirmation_email}. "
                    f"Booking `{session.booking_code}` on {session.chosen_slot.date} at "
                    f"{session.chosen_slot.time} IST."
                )
                st.session_state.messages.append({"role": "assistant", "content": confirmation_msg})
                st.success("Email confirmation sent successfully.")
                st.rerun()
            else:
                st.error(f"Failed to send email confirmation: {send_result.error}")
