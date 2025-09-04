import os 
import tempfile
import streamlit as st
import traceback 
from langchain.chains import RetrievalQA
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_groq import ChatGroq
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from langchain_core.prompts import PromptTemplate
from dotenv import load_dotenv
from langchain.memory import ConversationBufferMemory
from langchain.chains import ConversationalRetrievalChain

from pdf_utils import save_uploaded_file, load_and_chunk_pdf, append_chunks_to_faiss
from langchain.retrievers import EnsembleRetriever

# Import user input handlers
from user_input_handler import (
    initialize_session_state,
    get_user_input,
    display_past_messages,
    add_message
)


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

Conversational History:
{chat_history}

Context: {context}
Question: {question}

Answer:
"""



def set_custom_prompt(template: str) -> PromptTemplate:
    return PromptTemplate(template=template, input_variables=["chat_history", "context", "question"])



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
        temperature=0.6,
        max_tokens=512
    )

def main():
    st.set_page_config(page_title="MurphyBot - Medical QA", layout="centered")
    st.title("Ask MurphyBot")

    initialize_session_state()
    display_past_messages()

    # ==== PDF UPLOAD HANDLING (3 max, 10MB each, session-only) ====
    uploaded_pdfs = st.file_uploader(
        "Upload up to 3 PDF medical reports (max 10MB each, optional)", 
        type=["pdf"], 
        accept_multiple_files=True,
        key="pdf_upload"
    )
    MAX_PDFS = 3
    MAX_SIZE_MB = 10

    if uploaded_pdfs:
        if len(uploaded_pdfs) > MAX_PDFS:
            st.error("You can upload a maximum of 3 PDFs per session.")
            uploaded_pdfs = uploaded_pdfs[:MAX_PDFS]

        # Session-only, accumulate all PDF chunks in one FAISS
        if "pdf_faiss" not in st.session_state:
            st.session_state["pdf_faiss"] = None

        for uploaded_file in uploaded_pdfs:
            if uploaded_file.size > MAX_SIZE_MB * 1024 * 1024:
                st.warning(f"{uploaded_file.name} exceeds 10MB and was not added.")
                continue
            # Save to a temp file to pass to PyPDFLoader
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmpfile:
                tmpfile.write(uploaded_file.read())
                tmpfile.flush()
                tmp_pdf_path = tmpfile.name
            # Each chunk tagged with filename
            chunks = load_and_chunk_pdf(tmp_pdf_path, uploaded_file.name)
            st.session_state["pdf_faiss"] = append_chunks_to_faiss(
                st.session_state["pdf_faiss"],
                chunks,
                EMBEDDING_MODEL_NAME
            )
            os.remove(tmp_pdf_path)  # Clean up temp file

        st.success(f"{len(uploaded_pdfs)} PDF(s) loaded for this session.")

    user_input = get_user_input()

    # ==== MEMORY ====
    if "memory" not in st.session_state:
        st.session_state.memory = ConversationBufferMemory(
            memory_key="chat_history",
            input_key="question",
            output_key="answer",
            return_messages=True
        )
    memory = st.session_state.memory

    if user_input:
        st.chat_message("user").markdown(user_input)
        add_message("user", user_input)

        try:
            vectorstore = get_vectorstore()
            persistent_retriever = vectorstore.as_retriever(search_kwargs={"k": 3})

            # ==== COMBINE KB + PDF FAISS ====
            if st.session_state.get("pdf_faiss"):
                pdf_retriever = st.session_state["pdf_faiss"].as_retriever(search_kwargs={"k": 3})
                combined_retriever = EnsembleRetriever(
                    retrievers=[persistent_retriever, pdf_retriever],
                    weights=[0.7, 0.3]
                )
            else:
                combined_retriever = persistent_retriever

            llm = load_llm()
            qa_chain = ConversationalRetrievalChain.from_llm(
                llm=llm,
                retriever=combined_retriever,
                memory=memory,
                combine_docs_chain_kwargs={"prompt": set_custom_prompt(CUSTOM_PROMPT_TEMPLATE)},
                return_source_documents=True,
            )

            response = qa_chain.invoke({"question": user_input})
            answer = response["answer"]
            source_docs = response["source_documents"]

            doc_display = "\n\n".join([
                f"Source {i+1}: {doc.metadata.get('source', 'N/A')}"
                for i, doc in enumerate(source_docs)
            ])

            full_output = f"{answer}\n\n---\n{doc_display}"
            st.chat_message("assistant").markdown(full_output)
            add_message("assistant", full_output)

        except Exception as e:
            st.error("An error occurred while processing your request.")
            st.code(traceback.format_exc(), language="python")

if __name__ == "__main__":
    main()
