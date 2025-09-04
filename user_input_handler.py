import streamlit as st

def initialize_session_state():
    """Initial chat session state if not already set."""
    if "messages" not in st.session_state:
        st.session_state.messages = []


def get_user_input():
    """Display chat input bot and return user input string (or None)"""
    return st.chat_input("Hi, I am Dr.Murphy. Go Ahead and ask me a question")

def display_past_messages():
    """Render past messages in the chat window"""
    for msg in st.session_state.messages:
        st.chat_message(msg["role"]).markdown(msg["content"])

def add_message(role, content):
    """Add a message (user or assistant) to the session state"""
    st.session_state.messages.append({"role": role,
                                     "content":content})


