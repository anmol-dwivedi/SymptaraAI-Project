import os
import streamlit as st
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_huggingface import HuggingFaceEmbeddings
from langchain.chains import RetrievalQA
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from langchain_core.prompts import PromptTemplate
import traceback

# Load .env
load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
COLLECTION_NAME = "medibot_memory"

EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
GROQ_MODEL_NAME = "llama-3.3-70b-versatile"  

CUSTOM_PROMPT_TEMPLATE = """
You are a medical consultant. Use the context to answer the question.
If you don't know the answer, say so. Do not guess.

Context: {context}
Question: {question}

Answer:
"""

def set_custom_prompt(template: str) -> PromptTemplate:
    return PromptTemplate(template=template, input_variables=["context", "question"])

@st.cache_resource
def get_vectorstore():
    embedding = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL_NAME)
    client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
    return QdrantVectorStore(
        client=client,
        collection_name=COLLECTION_NAME,
        embedding=embedding,
    )

def load_llm():
    return ChatGroq(
        model_name=GROQ_MODEL_NAME,
        groq_api_key=GROQ_API_KEY,
        temperature=0.4,
        max_tokens=1024
    )

def main():
    st.set_page_config(page_title="MurphyBot - Medical QA", layout="centered")
    st.title("Ask MurphyBot")

    if "messages" not in st.session_state:
        st.session_state.messages = []

    for msg in st.session_state.messages:
        st.chat_message(msg["role"]).markdown(msg["content"])

    user_input = st.chat_input("Ask a medical question")

    if user_input:
        st.chat_message("user").markdown(user_input)
        st.session_state.messages.append({"role": "user", "content": user_input})

        try:
            vectorstore = get_vectorstore()
            llm = load_llm()

            qa_chain = RetrievalQA.from_chain_type(
                llm=llm,
                chain_type="stuff",
                retriever=vectorstore.as_retriever(search_kwargs={"k": 3}),
                return_source_documents=True,
                chain_type_kwargs={"prompt": set_custom_prompt(CUSTOM_PROMPT_TEMPLATE)}
            )

            response = qa_chain.invoke({"query": user_input})
            answer = response["result"]
            source_docs = response["source_documents"]

            doc_display = "\n\n".join([
                f"Source {i+1}: {doc.metadata.get('source', 'N/A')}"
                for i, doc in enumerate(source_docs)
            ])

            full_output = f"{answer}\n\n---\n{doc_display}"
            st.chat_message("assistant").markdown(full_output)
            st.session_state.messages.append({"role": "assistant", "content": full_output})

        except Exception as e:
            st.error("An error occurred while processing your request.")
            st.code(traceback.format_exc(), language="python")

if __name__ == "__main__":
    main()
