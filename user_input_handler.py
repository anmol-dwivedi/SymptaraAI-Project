import streamlit as st

try:
    from streamlit_mic_recorder import mic_recorder
    MIC_RECORDER_AVAILABLE = True
except ImportError:
    MIC_RECORDER_AVAILABLE = False

def initialize_session_state():
    if "messages" not in st.session_state:
        st.session_state.messages = []

def display_past_messages():
    for msg in st.session_state.messages:
        st.chat_message(msg["role"]).markdown(msg["content"])

def add_message(role, content):
    st.session_state.messages.append({"role": role, "content": content})

def get_user_input():
    return st.chat_input("Hi, I am Dr.Murphy. Go Ahead and ask me a question")

def get_voice_input(transcribe_func, prompt="🎤 Speak to MurphyBot", stop="Stop", key="mic"):
    if not MIC_RECORDER_AVAILABLE:
        return None

    audio_data = mic_recorder(
        start_prompt=prompt,
        stop_prompt=stop,
        key=key
    )
    transcript = None
    if audio_data and "audio" in audio_data and audio_data["audio"] is not None:
        temp_audio_path = "temp_audio.wav"
        with open(temp_audio_path, "wb") as f:
            f.write(audio_data["audio"])
        st.audio(audio_data["audio"], format="audio/wav")
        st.info("Transcribing audio...")

        try:
            transcript = transcribe_func(temp_audio_path)
            if transcript.strip():
                st.success(f"You said: {transcript}")
            else:
                st.warning("Sorry, I could not understand your speech. Please try again.")
        except Exception as e:
            st.error(f"Transcription failed: {e}")

    return transcript

def get_chatbot_input(transcribe_func=None, prefer_voice=True):
    user_input = None
    if prefer_voice and transcribe_func and MIC_RECORDER_AVAILABLE:
        user_input = get_voice_input(transcribe_func)
    if not user_input:  # fallback to text input if not spoken or mic unavailable
        user_input = get_user_input()
    return user_input
