import os
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_qdrant import QdrantVectorStore
from langchain_core.prompts import PromptTemplate
from langchain_huggingface import HuggingFaceEmbeddings
from langchain.chains import RetrievalQA
from qdrant_client import QdrantClient

# Load environment
load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
COLLECTION_NAME = "medibot_memory"

CUSTOM_PROMPT_TEMPLATE = """
You are a medical consultant. Use the context to answer the question.
If you don't know the answer, say so. Do not guess.

Context: {context}
Question: {question}

Answer:
"""

def set_custom_prompt():
    """Returns the prompt template for the LLM."""
    return PromptTemplate(template=CUSTOM_PROMPT_TEMPLATE, input_variables=["context", "question"])

def load_rag_chain():
    """Initializes and returns the RAG chain with Qdrant and Groq."""
    embedding = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
    vectorstore = QdrantVectorStore(client=client, collection_name=COLLECTION_NAME, embedding=embedding)

    llm = ChatGroq(
        model_name="llama-3.3-70b-versatile",
        groq_api_key=GROQ_API_KEY,
        temperature=0.4,
        max_tokens=1024
    )

    return RetrievalQA.from_chain_type(
        llm=llm,
        chain_type="stuff",
        retriever=vectorstore.as_retriever(search_kwargs={"k": 3}),
        return_source_documents=True,
        chain_type_kwargs={"prompt": set_custom_prompt()}
    )