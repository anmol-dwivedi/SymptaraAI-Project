import os
import time
from dotenv import load_dotenv
from langchain_community.document_loaders import PyPDFLoader, DirectoryLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient

# Load environment variables
load_dotenv()
QDRANT_URL = os.environ.get("QDRANT_URL")
QDRANT_API_KEY = os.environ.get("QDRANT_API_KEY")
COLLECTION_NAME = "medibot_memory"
DATA_PATH = "Books/"

def load_pdf_files(path: str):
    loader = DirectoryLoader(path, glob="*.pdf", loader_cls=PyPDFLoader)
    return loader.load()

def create_chunks(docs):
    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    return splitter.split_documents(docs)

def get_embeddings():
    return HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")

def main():
    print("Loading PDFs...")
    documents = load_pdf_files(DATA_PATH)
    print(f"Loaded {len(documents)} documents")

    print("Splitting into chunks...")
    chunks = create_chunks(documents)
    print(f"Created {len(chunks)} text chunks")

    print("Uploading embeddings to Qdrant...")
    embedding = get_embeddings()
    client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)

    QdrantVectorStore.from_documents(
        documents=chunks,
        embedding=embedding,
        client=client,
        collection_name=COLLECTION_NAME
    )

    print(f"Successfully indexed {len(chunks)} chunks into collection '{COLLECTION_NAME}'")

if __name__ == "__main__":
    start = time.time()
    main()
    print(f"Finished in {round(time.time() - start, 2)} seconds")
