import streamlit as st
import whisper
import os

@st.cache_resource
def load_whisper_model():
    return whisper.load_model("base")

model = load_whisper_model()

st.title("MurphyBot: Speak & Transcribe Demo (Native Streamlit Audio)")

audio_file = st.audio_input("🎤 Click to record your question to MurphyBot")

if audio_file is not None:
    audio_save_path = "recorded_query.wav"
    with open(audio_save_path, "wb") as f:
        f.write(audio_file.getbuffer())

    st.success("Audio recorded. Now transcribing with Whisper...")

    result = model.transcribe(audio_save_path)
    transcript = result["text"]
    st.markdown("**Transcription:**")
    st.write(transcript)
else:
    st.info("Click above to record your query for MurphyBot.")
