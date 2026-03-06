"""
embed_books.py — MurphyBot Data Pipeline
Chunks 16 Docling-parsed .md files at H2 headings and embeds them
into ChromaDB collection: medical_books

Usage:
    python embed_books.py

Requirements:
    pip install chromadb openai python-dotenv tqdm
"""

import os
import re
import hashlib
import logging
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from tqdm import tqdm

import chromadb
from chromadb.utils import embedding_functions

load_dotenv()

# ── Logging ───────────────────────────────────────────────────────────────────

LOG_FOLDER = Path("./logs")
LOG_FOLDER.mkdir(exist_ok=True)

log_filename = LOG_FOLDER / f"embed_books_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(log_filename),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────

MD_FOLDER   = os.getenv("MD_FOLDER", "./docling_output")
CHROMA_PATH = os.getenv("CHROMA_PATH", "./chroma_db")
COLLECTION  = "medical_books"

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
EMBED_MODEL    = "text-embedding-3-small"

MIN_CHUNK_CHARS = 150
MAX_CHUNK_CHARS = 6000  # ~1500 tokens

BATCH_SIZE = 50


# ── Chunking ──────────────────────────────────────────────────────────────────

def chunk_by_h2(text: str, source_file: str) -> list[dict]:
    """
    Split markdown at H2 headings (## ...).
    Falls back to H3 split if an H2 section is still oversized.
    """
    parts = re.split(r"(?=^## )", text, flags=re.MULTILINE)

    chunks = []
    chunk_index = 0

    for part in parts:
        part = part.strip()
        if not part:
            continue

        first_line = part.splitlines()[0]
        heading = first_line.strip("# ").strip() if first_line.startswith("#") else "Introduction"

        sub_parts = re.split(r"(?=^### )", part, flags=re.MULTILINE) if len(part) > MAX_CHUNK_CHARS else [part]

        for sub in sub_parts:
            sub = sub.strip()
            if len(sub) < MIN_CHUNK_CHARS:
                continue

            if len(sub) > MAX_CHUNK_CHARS:
                sub = sub[:MAX_CHUNK_CHARS]

            chunks.append({
                "text":        sub,
                "heading":     heading,
                "source_file": source_file,
                "chunk_index": chunk_index,
            })
            chunk_index += 1

    return chunks


def load_all_chunks(md_folder: str) -> list[dict]:
    """Walk MD_FOLDER, parse every .md file, return all chunks."""
    folder = Path(md_folder)
    md_files = sorted(folder.glob("*.md"))

    if not md_files:
        raise FileNotFoundError(
            f"No .md files found in {md_folder!r}. Check MD_FOLDER in your .env."
        )

    log.info(f"Found {len(md_files)} .md files in '{md_folder}'")

    all_chunks = []
    for md_file in md_files:
        text = md_file.read_text(encoding="utf-8", errors="replace")
        chunks = chunk_by_h2(text, source_file=md_file.name)
        log.info(f"  Parsed: {md_file.name} -> {len(chunks)} chunks")
        all_chunks.extend(chunks)

    log.info(f"Total chunks before dedup: {len(all_chunks)}")
    return all_chunks


# ── Deduplication ─────────────────────────────────────────────────────────────

def dedup_chunks(chunks: list[dict]) -> list[dict]:
    """Remove exact-duplicate text blocks."""
    seen = set()
    unique = []
    for chunk in chunks:
        h = hashlib.md5(chunk["text"].encode()).hexdigest()
        if h not in seen:
            seen.add(h)
            unique.append(chunk)

    removed = len(chunks) - len(unique)
    if removed:
        log.warning(f"Removed {removed} duplicate chunks.")
    else:
        log.info("No duplicate chunks found.")

    log.info(f"Final chunk count after dedup: {len(unique)}")
    return unique


# ── ChromaDB ──────────────────────────────────────────────────────────────────

def build_chroma_collection(chunks: list[dict]) -> None:
    """Embed chunks and upsert into ChromaDB medical_books collection."""

    if not OPENAI_API_KEY:
        raise EnvironmentError("OPENAI_API_KEY not set in .env")

    ef = embedding_functions.OpenAIEmbeddingFunction(
        api_key=OPENAI_API_KEY,
        model_name=EMBED_MODEL,
    )

    client = chromadb.PersistentClient(path=CHROMA_PATH)

    existing = [c.name for c in client.list_collections()]
    if COLLECTION in existing:
        log.warning(f"Collection '{COLLECTION}' already exists - deleting for clean rebuild.")
        client.delete_collection(COLLECTION)

    collection = client.create_collection(
        name=COLLECTION,
        embedding_function=ef,
        metadata={"hnsw:space": "cosine"},
    )

    estimated_cost = len(chunks) * 400 / 1_000_000 * 0.02
    log.info(f"Embedding {len(chunks)} chunks | Model: {EMBED_MODEL} | Batch size: {BATCH_SIZE}")
    log.info(f"Estimated OpenAI embedding cost: ~${estimated_cost:.4f}")

    total_batches = (len(chunks) + BATCH_SIZE - 1) // BATCH_SIZE

    for i in tqdm(range(0, len(chunks), BATCH_SIZE), desc="Embedding batches", total=total_batches):
        batch = chunks[i : i + BATCH_SIZE]

        ids       = [f"{c['source_file']}__chunk_{c['chunk_index']}" for c in batch]
        documents = [c["text"] for c in batch]
        metadatas = [
            {
                "source_file": c["source_file"],
                "heading":     c["heading"],
                "chunk_index": c["chunk_index"],
                "char_count":  len(c["text"]),
            }
            for c in batch
        ]

        collection.add(ids=ids, documents=documents, metadatas=metadatas)
        log.info(f"  Batch {i // BATCH_SIZE + 1}/{total_batches} upserted ({len(batch)} chunks)")

    log.info(f"Embedding complete. {collection.count()} chunks stored in '{COLLECTION}'.")


# ── Smoke test ────────────────────────────────────────────────────────────────

def smoke_test() -> None:
    """Run 3 retrieval queries to confirm the collection works."""
    ef = embedding_functions.OpenAIEmbeddingFunction(
        api_key=OPENAI_API_KEY,
        model_name=EMBED_MODEL,
    )
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    collection = client.get_collection(name=COLLECTION, embedding_function=ef)

    test_queries = [
        "fever headache stiff neck",
        "chest pain shortness of breath",
        "antibiotic treatment bacterial infection",
    ]

    log.info("Smoke Test starting...")
    all_passed = True

    for query in test_queries:
        results = collection.query(
            query_texts=[query],
            n_results=3,
            include=["documents", "metadatas", "distances"],
        )
        hits = results["documents"][0]
        if not hits:
            log.error(f"FAIL - no results for query: {query!r}")
            all_passed = False
            continue

        log.info(f"Query: {query!r}")
        for doc, meta, dist in zip(hits, results["metadatas"][0], results["distances"][0]):
            log.info(f"  [{dist:.3f}] {meta['source_file']} > {meta['heading']}")
            log.info(f"         {doc[:120].strip()}...")

    if all_passed:
        log.info("Smoke test PASSED - all 3 queries returned results.")
    else:
        log.error("Smoke test FAILED - check logs above.")


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    log.info("=" * 60)
    log.info("MurphyBot - embed_books.py starting")
    log.info(f"Log file: {log_filename}")
    log.info("=" * 60)

    start = datetime.now()

    chunks = load_all_chunks(MD_FOLDER)
    chunks = dedup_chunks(chunks)
    build_chroma_collection(chunks)
    smoke_test()

    elapsed = datetime.now() - start
    log.info(f"Total runtime: {elapsed}")
    log.info("Next step: run embed_hpo.py to build the hpo_terms collection.")