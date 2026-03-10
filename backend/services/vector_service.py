import chromadb
from langsmith import traceable
from config import settings

chroma_client = chromadb.PersistentClient(path=settings.chroma_path)
books_collection = chroma_client.get_collection("medical_books")


@traceable(name="vector-book-search")
def search_medical_books(query: str, top_k: int = 5) -> list[dict]:
    """
    Semantic search over the 16 embedded medical books.
    Returns the most clinically relevant chunks for a symptom query.

    Args:
        query: Natural language symptom description
               e.g. "fever headache neck stiffness photophobia"
        top_k: Number of chunks to return (default 5)

    Returns:
        [
            {
                "text": "Bacterial meningitis presents with...",
                "source_book": "Harrisons Principles",
                "chapter": "Infectious Diseases",
                "distance": 0.21
            },
            ...
        ]
    """
    results = books_collection.query(
        query_texts=[query],
        n_results=top_k,
        include=["documents", "metadatas", "distances"]
    )

    if not results["ids"][0]:
        return []

    chunks = []
    for i in range(len(results["ids"][0])):
        metadata = results["metadatas"][0][i]
        chunks.append({
            "text":        results["documents"][0][i],
            "source_book": metadata.get("source_book", "Unknown"),
            "chapter":     metadata.get("chapter", ""),
            "section":     metadata.get("section_title", ""),
            "chunk_id":    metadata.get("chunk_id", ""),
            "distance":    round(results["distances"][0][i], 3)
        })

    return chunks


@traceable(name="vector-multi-query-search")
def search_books_multi_query(symptom_list: list[str], top_k: int = 5) -> list[dict]:
    """
    Runs multiple targeted queries and deduplicates results.
    Better coverage than a single combined query for 3+ symptoms.

    Args:
        symptom_list: Individual symptoms e.g. ["fever", "neck stiffness"]
        top_k:        Total chunks to return after dedup

    Returns:
        Same format as search_medical_books, deduplicated by chunk_id
    """
    if not symptom_list:
        return []

    seen_ids = set()
    all_chunks = []

    # Query 1: all symptoms combined
    combined_query = " ".join(symptom_list)
    for chunk in search_medical_books(combined_query, top_k=top_k):
        cid = chunk["chunk_id"]
        if cid not in seen_ids:
            seen_ids.add(cid)
            all_chunks.append(chunk)

    # Query 2: each symptom individually (catches niche chapters)
    for symptom in symptom_list[:3]:  # cap at 3 to avoid too many calls
        for chunk in search_medical_books(symptom, top_k=2):
            cid = chunk["chunk_id"]
            if cid not in seen_ids:
                seen_ids.add(cid)
                all_chunks.append(chunk)

    # Sort by distance (lower = more relevant) and return top_k
    all_chunks.sort(key=lambda x: x["distance"])
    return all_chunks[:top_k]


def format_chunks_for_prompt(chunks: list[dict], max_chars: int = 3000) -> str:
    """
    Formats retrieved chunks into a clean string for Claude's context window.
    Truncates to max_chars to avoid bloating the prompt.

    Used by context_assembler to inject book knowledge into the triage prompt.
    """
    if not chunks:
        return "No relevant clinical references found."

    lines = []
    total = 0
    for i, chunk in enumerate(chunks, 1):
        header = f"[{i}] {chunk['source_book']}"
        if chunk["chapter"]:
            header += f" — {chunk['chapter']}"
        block = f"{header}\n{chunk['text']}\n"
        if total + len(block) > max_chars:
            break
        lines.append(block)
        total += len(block)

    return "\n".join(lines)