"""
Phase 6: A premium, glassmorphism Voice Web UI for the Advisor Agent.
Uses Gradio, SpeechRecognition (free Google STT), and edge-tts (premium Microsoft TTS).
"""
import asyncio
import os
import uuid
import requests
import speech_recognition as sr
import edge_tts
import gradio as gr

API_URL = "http://127.0.0.1:8000"

# Styling matching the "WOW" aesthetics request
CUSTOM_CSS = """
body {
    background: linear-gradient(-45deg, #0f172a, #1e1b4b, #312e81, #0f172a);
    background-size: 400% 400%;
    animation: gradientBG 15s ease infinite;
    font-family: 'Inter', sans-serif !important;
}
@keyframes gradientBG {
    0% { background-position: 0% 50%; }
    50% { background-position: 100% 50%; }
    100% { background-position: 0% 50%; }
}
div.gradio-container {
    background: transparent !important;
    border: none !important;
}
.glass-container {
    background: rgba(255, 255, 255, 0.05) !important;
    backdrop-filter: blur(16px) !important;
    -webkit-backdrop-filter: blur(16px);
    border: 1px solid rgba(255, 255, 255, 0.1) !important;
    border-radius: 20px !important;
    box-shadow: 0 4px 30px rgba(0, 0, 0, 0.2) !important;
    padding: 2rem !important;
}
.header-text {
    color: #f8fafc;
    text-align: center;
    font-weight: 800;
    font-size: 2.8rem;
    letter-spacing: -1px;
    margin-bottom: 0px;
    background: -webkit-linear-gradient(45deg, #38bdf8, #a78bfa);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}
.sub-text {
    color: #cbd5e1;
    text-align: center;
    font-size: 1.1rem;
    margin-bottom: 20px;
}
"""

def init_session():
    """Start a new session on load and auto-play the greeting from the backend."""
    try:
        res = requests.post(f"{API_URL}/session")
        if res.status_code == 200:
            session_id = res.json()["session_id"]
            # Trigger greeting from FSM
            msg_res = requests.post(f"{API_URL}/message", json={"session_id": session_id, "text": ""})
            responses = msg_res.json().get("responses", [])
            initial_text = " ".join(responses)
            
            # Generate speech for greeting
            greeting_audio = asyncio.run(text_to_speech(initial_text))
            
            history = [{"role": "assistant", "content": initial_text}]
            return session_id, history, greeting_audio
    except Exception as e:
        return "", [{"role": "assistant", "content": f"Failed to connect to backend: {e}"}], None

async def text_to_speech(text: str) -> str:
    """Uses Microsoft edge-tts (free, premium) to generate Indian English voice."""
    voice = "en-IN-NeerjaNeural"
    output_file = f"response_{uuid.uuid4().hex}.mp3"
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output_file)
    return output_file

def transcribe_audio(audio_path: str) -> str:
    """Uses SpeechRecognition to transcribe the WAV file from the browser mic."""
    if not audio_path: return ""
    recognizer = sr.Recognizer()
    try:
        with sr.AudioFile(audio_path) as source:
            audio_data = recognizer.record(source)
            text = recognizer.recognize_google(audio_data, language="en-IN")
            return text
    except Exception as e:
        print(f"STT Error: {e}")
        return ""

async def process_turn(audio_path, session_id, history):
    if not session_id or not audio_path:
        yield history, None, None
        return

    # 1. Transcribe Voice (Ear)
    user_text = transcribe_audio(audio_path)
    if not user_text:
        yield history, None, None
        return
        
    history.append({"role": "user", "content": user_text})
    yield history, None, None  # Update screen immediately with transcribed text

    # 2. Get Backend Response (Brain)
    try:
        res = requests.post(f"{API_URL}/message", json={
            "session_id": session_id,
            "text": user_text
        })
        data = res.json()
        joined_responses = " ".join(data["responses"])
        
        history.append({"role": "assistant", "content": joined_responses})
        yield history, None, None  # Update screen with assistant text
        
        # 3. Text to Speech (Mouth)
        audio_file = await text_to_speech(joined_responses)
        yield history, audio_file, None  # Return audio to auto-play and clear mic
        
    except Exception as e:
        history.append({"role": "assistant", "content": f"Backend Error: {str(e)}"})
        yield history, None, None

with gr.Blocks() as demo:
    session_id_state = gr.State("")
    
    with gr.Column(elem_classes=["glass-container"]):
        gr.Markdown("<h1 class='header-text'>Advisor Voice Agent</h1>")
        gr.Markdown("<p class='sub-text'>Hands-free compliant appointment scheduling.</p>")
        
        chatbot = gr.Chatbot(height=450)
        
        # Audio auto-player hidden helper
        audio_out = gr.Audio(visible=False, autoplay=True)
        
        with gr.Row():
            mic_input = gr.Audio(sources=["microphone"], type="filepath", format="wav", label="Microphone (Click to Speak, Stop to Send)")

        # Initialization
        demo.load(init_session, outputs=[session_id_state, chatbot, audio_out])
        
        # Interaction Trigger
        mic_input.stop_recording(
            fn=process_turn,
            inputs=[mic_input, session_id_state, chatbot],
            outputs=[chatbot, audio_out, mic_input], # output mic_input to None resets
        )

if __name__ == "__main__":
    print("Starting Voice UI server on port 7860...")
    theme = gr.themes.Soft(primary_hue="indigo")
    demo.launch(server_name="127.0.0.1", server_port=7860, theme=theme, css=CUSTOM_CSS)
