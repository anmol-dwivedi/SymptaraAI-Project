"""
embed_hpo.py — MurphyBot Data Pipeline
Downloads the HPO ontology (hp.obo), parses all phenotype terms,
and embeds them into ChromaDB collection: hpo_terms

Each embedded document = "HP:xxxxxxx | term name | definition"
This gives the vector fallback in hpo_mapper.py enough signal to map
vague patient language ("splitting headache worse in morning") to HPO IDs.

Usage:
    python embed_hpo.py

Requirements:
    pip install chromadb openai python-dotenv tqdm requests
"""

import os
import re
import logging
import requests
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

log_filename = LOG_FOLDER / f"embed_hpo_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

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

CHROMA_PATH    = os.getenv("CHROMA_PATH", "./chroma_db")
COLLECTION     = "hpo_terms"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
EMBED_MODEL    = "text-embedding-3-small"
BATCH_SIZE     = 100  # HPO docs are short — larger batches are fine

# HPO ontology — official OBO flat file from JAX
HPO_OBO_URL  = "https://github.com/obophenotype/human-phenotype-ontology/releases/latest/download/hp.obo"
HPO_OBO_PATH = Path("./hp.obo")  # cached locally after first download


# ── Download ──────────────────────────────────────────────────────────────────

def download_hpo_obo() -> Path:
    """Download hp.obo if not already cached locally."""
    if HPO_OBO_PATH.exists():
        log.info(f"hp.obo already exists at {HPO_OBO_PATH} — skipping download.")
        return HPO_OBO_PATH

    log.info(f"Downloading HPO ontology from {HPO_OBO_URL} ...")
    log.info("File size is ~8MB — should take under a minute.")

    response = requests.get(HPO_OBO_URL, stream=True, timeout=120)
    response.raise_for_status()

    total = int(response.headers.get("content-length", 0))
    downloaded = 0

    with open(HPO_OBO_PATH, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
            downloaded += len(chunk)

    log.info(f"Download complete. File size: {downloaded / 1_000_000:.1f} MB")
    return HPO_OBO_PATH


# ── OBO Parser ────────────────────────────────────────────────────────────────

def parse_obo(obo_path: Path) -> list[dict]:
    """
    Parse hp.obo into a list of HPO term dicts.
    Extracts: id, name, definition, synonyms, is_obsolete flag.
    Skips obsolete terms — they pollute retrieval with outdated mappings.
    """
    terms = []
    current = {}

    with open(obo_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()

            if line == "[Term]":
                if current:
                    terms.append(current)
                current = {"synonyms": []}
                continue

            if not current:
                continue

            if line.startswith("id: "):
                current["id"] = line[4:].strip()

            elif line.startswith("name: "):
                current["name"] = line[6:].strip()

            elif line.startswith("def: "):
                # def: "Some definition text." [source1, source2]
                match = re.match(r'def: "(.+?)"', line)
                current["definition"] = match.group(1) if match else ""

            elif line.startswith("synonym: "):
                # synonym: "Fever" EXACT [...]
                match = re.match(r'synonym: "(.+?)"', line)
                if match:
                    current["synonyms"].append(match.group(1))

            elif line.startswith("is_obsolete: true"):
                current["is_obsolete"] = True

    # Don't forget the last block
    if current:
        terms.append(current)

    # Filter: keep only proper HP terms, drop obsolete
    valid = [
        t for t in terms
        if t.get("id", "").startswith("HP:")
        and not t.get("is_obsolete", False)
        and t.get("name")
    ]

    log.info(f"Parsed {len(terms)} total OBO blocks -> {len(valid)} valid HP terms (obsolete removed)")
    return valid


# ── Document Builder ──────────────────────────────────────────────────────────

def build_documents(terms: list[dict]) -> tuple[list[str], list[str], list[dict]]:
    """
    Build ChromaDB-ready (ids, documents, metadatas) from parsed HPO terms.

    Document format (maximises semantic retrieval):
        "HP:0001945 | Fever | Elevated body temperature above normal range.
         Also known as: Elevated temperature, Hyperthermia, Pyrexia"

    Packing the HPO ID + name + definition + synonyms into one string means
    both clinical terms AND patient language ("burning up", "high temp") have
    a chance to match via cosine similarity.
    """
    ids, documents, metadatas = [], [], []

    for term in terms:
        hpo_id     = term["id"]
        name       = term.get("name", "")
        definition = term.get("definition", "")
        synonyms   = term.get("synonyms", [])

        # Build rich text for embedding
        parts = [f"{hpo_id} | {name}"]
        if definition:
            parts.append(definition)
        if synonyms:
            parts.append("Also known as: " + ", ".join(synonyms[:8]))  # cap at 8 synonyms

        document = " | ".join(parts)

        ids.append(hpo_id)
        documents.append(document)
        metadatas.append({
            "hpo_id":          hpo_id,
            "name":            name,
            "definition":      definition[:300],  # truncate for metadata storage
            "synonym_count":   len(synonyms),
        })

    return ids, documents, metadatas


# ── ChromaDB ──────────────────────────────────────────────────────────────────

def build_chroma_collection(ids: list[str], documents: list[str], metadatas: list[dict]) -> None:
    """Embed HPO term documents and upsert into ChromaDB hpo_terms collection."""

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

    # HPO term docs average ~80 tokens — cost is very low
    estimated_cost = len(documents) * 80 / 1_000_000 * 0.02
    log.info(f"Embedding {len(documents)} HPO terms | Model: {EMBED_MODEL} | Batch size: {BATCH_SIZE}")
    log.info(f"Estimated OpenAI embedding cost: ~${estimated_cost:.4f}")

    total_batches = (len(documents) + BATCH_SIZE - 1) // BATCH_SIZE

    for i in tqdm(range(0, len(documents), BATCH_SIZE), desc="Embedding batches", total=total_batches):
        batch_ids  = ids[i : i + BATCH_SIZE]
        batch_docs = documents[i : i + BATCH_SIZE]
        batch_meta = metadatas[i : i + BATCH_SIZE]

        collection.add(ids=batch_ids, documents=batch_docs, metadatas=batch_meta)
        log.info(f"  Batch {i // BATCH_SIZE + 1}/{total_batches} upserted ({len(batch_ids)} terms)")

    log.info(f"Embedding complete. {collection.count()} HPO terms stored in '{COLLECTION}'.")


# ── Smoke test ────────────────────────────────────────────────────────────────

def smoke_test() -> None:
    """
    Test retrieval with patient-language queries.
    These are intentionally NOT clinical terms — they simulate what hpo_mapper.py
    will receive when a patient types "splitting headache" instead of "Headache".
    """
    ef = embedding_functions.OpenAIEmbeddingFunction(
        api_key=OPENAI_API_KEY,
        model_name=EMBED_MODEL,
    )
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    collection = client.get_collection(name=COLLECTION, embedding_function=ef)

    test_queries = [
        "splitting headache worse in morning",        # → HP:0002315 Headache
        "burning up high temperature",                # → HP:0001945 Fever
        "neck feels stiff hard to move",              # → HP:0031360 Neck stiffness
        "sensitive to bright light hurts eyes",       # → HP:0000613 Photophobia
        "throwing up feeling nauseous",               # → HP:0002013 Vomiting
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
            log.info(f"  [{dist:.3f}] {meta['hpo_id']} | {meta['name']}")

    if all_passed:
        log.info("Smoke test PASSED - all queries returned results.")
    else:
        log.error("Smoke test FAILED - check logs above.")


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    log.info("=" * 60)
    log.info("MurphyBot - embed_hpo.py starting")
    log.info(f"Log file: {log_filename}")
    log.info("=" * 60)

    start = datetime.now()

    # Step 1 — get the OBO file
    obo_path = download_hpo_obo()

    # Step 2 — parse into term dicts
    terms = parse_obo(obo_path)

    # Step 3 — build ChromaDB-ready documents
    ids, documents, metadatas = build_documents(terms)

    # Step 4 — embed and store
    build_chroma_collection(ids, documents, metadatas)

    # Step 5 — confirm retrieval works
    smoke_test()

    elapsed = datetime.now() - start
    log.info(f"Total runtime: {elapsed}")
    log.info("Day 1 data layer complete. Both collections ready:")
    log.info("  medical_books  — clinical book chunks")
    log.info("  hpo_terms      — HPO phenotype terms for symptom mapping")
    log.info("Next step: run verify_data.py, then move to Day 2 backend.")