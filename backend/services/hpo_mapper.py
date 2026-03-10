import json
import chromadb
import anthropic
from langsmith import traceable
from config import settings

client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

# Load the hpo_terms ChromaDB collection (embedded on Day 1)
chroma_client = chromadb.PersistentClient(path=settings.chroma_path)
hpo_collection = chroma_client.get_collection("hpo_terms")

SYSTEM_PROMPT = """You are a clinical ontology mapping engine.
Map each symptom to its HPO (Human Phenotype Ontology) term ID.

Rules:
- Only map symptoms you are highly confident about
- Use standard clinical HPO term IDs in format HP:XXXXXXX
- If you are unsure about a term, omit it — do NOT guess
- Return ONLY a JSON object, no explanation, no markdown

Output format:
{
  "mapped": {
    "fever": "HP:0001945",
    "headache": "HP:0002315"
  },
  "unmapped": ["unusual symptom", "vague complaint"]
}"""


@traceable(name="hpo-mapper-claude")
def _claude_map(symptoms: list[str]) -> dict:
    """Claude maps high-confidence symptoms to HPO IDs."""
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=512,
        system=SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": f"Map these symptoms to HPO IDs:\n{json.dumps(symptoms)}"
        }]
    )

    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        result = {"mapped": {}, "unmapped": symptoms}

    result.setdefault("mapped", {})
    result.setdefault("unmapped", [])
    return result


@traceable(name="hpo-mapper-vector-fallback")
def _vector_fallback(symptoms: list[str], top_k: int = 1) -> dict:
    """
    ChromaDB vector similarity fallback for symptoms Claude couldn't map.
    Queries the hpo_terms collection embedded on Day 1.
    Returns best HPO match per symptom with confidence score.
    """
    fallback_mapped = {}

    for symptom in symptoms:
        results = hpo_collection.query(
            query_texts=[symptom],
            n_results=top_k,
            include=["documents", "metadatas", "distances"]
        )

        if not results["ids"][0]:
            continue

        distance = results["distances"][0][0]
        # ChromaDB cosine distance: 0.0 = identical, 2.0 = opposite
        # Accept matches with distance < 0.6 (reasonable semantic similarity)
        if distance < 0.6:
            metadata = results["metadatas"][0][0]
            hpo_id = metadata.get("hpo_id", "")
            if hpo_id:
                fallback_mapped[symptom] = {
                    "hpo_id": hpo_id,
                    "matched_term": metadata.get("name", ""),
                    "distance": round(distance, 3),
                    "source": "vector_fallback"
                }

    return fallback_mapped


@traceable(name="hpo-mapper")
def map_symptoms_to_hpo(symptoms: list[str]) -> dict:
    """
    Hybrid HPO mapping pipeline.

    Step 1: Claude maps well-known clinical terms (fast, high confidence)
    Step 2: ChromaDB vector fallback for anything Claude skipped

    Args:
        symptoms: List of normalized symptom strings from symptom_extractor

    Returns:
        {
            "hpo_ids": ["HP:0001945", "HP:0002315", ...],   ← for Neo4j query
            "mapping_detail": {                              ← for debugging
                "fever":    {"hpo_id": "HP:0001945", "source": "claude"},
                "eye pain": {"hpo_id": "HP:0000648", "source": "vector_fallback",
                             "matched_term": "Ocular pain", "distance": 0.41}
            },
            "unmapped": ["symptom claude skipped and vector missed"]
        }
    """
    if not symptoms:
        return {"hpo_ids": [], "mapping_detail": {}, "unmapped": []}

    # Step 1: Claude maps high-confidence terms
    claude_result = _claude_map(symptoms)
    mapped = {
        sym: {"hpo_id": hpo_id, "source": "claude"}
        for sym, hpo_id in claude_result["mapped"].items()
    }
    still_unmapped = claude_result["unmapped"]

    # Step 2: Vector fallback for what Claude left unmapped
    if still_unmapped:
        fallback = _vector_fallback(still_unmapped)
        for sym, detail in fallback.items():
            mapped[sym] = detail
            still_unmapped = [s for s in still_unmapped if s != sym]

    # Flatten to a clean list of HPO IDs for graph_service
    hpo_ids = [v["hpo_id"] for v in mapped.values() if v.get("hpo_id")]

    return {
        "hpo_ids": hpo_ids,
        "mapping_detail": mapped,
        "unmapped": still_unmapped
    }