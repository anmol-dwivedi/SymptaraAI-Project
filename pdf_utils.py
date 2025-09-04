import os, sys, time
from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS

# read in the pdf
def save_uploaded_file(uploaded_file,
                       save_path="temp_uploaded.pdf"):
    with open(save_path, "wb") as f:
        f.write(uploaded_file.read())
    return save_path

def load_and_chunk_pdf(pdf_path, filename, chunk_size=500, chunk_overlap=50):
    loader = PyPDFLoader(pdf_path)
    docs = loader.load()
    splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    chunks = splitter.split_documents(docs)
    # Tag with filename for source display!
    for chunk in chunks:
        chunk.metadata["source"] = filename
    return chunks

def append_chunks_to_faiss(faiss_vs, new_chunks, embedding_model_name):
    embedding = HuggingFaceEmbeddings(model_name=embedding_model_name)
    if faiss_vs is None:
        faiss_vs = FAISS.from_documents(new_chunks, embedding)
    else:
        faiss_vs.add_documents(new_chunks)
    return faiss_vs

    