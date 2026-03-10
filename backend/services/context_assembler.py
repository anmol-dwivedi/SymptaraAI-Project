from services.symptom_extractor import extract_symptoms, get_all_positive_symptoms
from services.hpo_mapper import map_symptoms_to_hpo
from services.graph_service import get_top_candidates
from services.vector_service import search_books_multi_query, format_chunks_for_prompt
from services.memory_service import get_history, get_user_profile


def assemble_context(
    user_message: str,
    session_id: str,
    user_id: str,
    accumulated_symptoms: list[str] = None,
    file_analysis: str = None
) -> dict:
    """
    Full hybrid RAG pipeline. Called once per user turn.

    Steps:
        1. Extract symptoms from latest message
        2. Merge with accumulated symptoms from session history
        3. Map symptoms → HPO IDs
        4. Query Neo4j graph → ranked disease candidates
        5. Query ChromaDB books → relevant clinical chunks
        6. Load user profile from Supabase
        7. Load conversation history
        8. Return everything assembled and ready for triage_controller

    Args:
        user_message:         Latest message from user
        session_id:           Current session UUID
        user_id:              User UUID
        accumulated_symptoms: Symptoms collected in previous turns
        file_analysis:        Claude vision output if image/PDF was uploaded

    Returns:
        {
            "new_symptoms":       list[str],   ← from this turn only
            "all_symptoms":       list[str],   ← all turns combined
            "hpo_ids":            list[str],
            "graph_candidates":   list[dict],
            "vector_chunks":      list[dict],
            "vector_context":     str,          ← formatted for prompt
            "user_profile":       dict | None,
            "conversation_history": list[dict],
            "file_analysis":      str | None,
            "extraction_detail":  dict          ← duration, severity, negations
        }
    """
    # ── Step 1: Extract symptoms from this message ────────────────────────────
    history = get_history(session_id)
    extraction = extract_symptoms(user_message, conversation_history=history)
    new_symptoms = get_all_positive_symptoms(extraction)

    # ── Step 2: Merge with accumulated symptoms ───────────────────────────────
    prior = accumulated_symptoms or []
    all_symptoms = _merge_symptoms(prior, new_symptoms)

    # ── Step 3: Map to HPO IDs ────────────────────────────────────────────────
    hpo_result = map_symptoms_to_hpo(all_symptoms) if all_symptoms else {}
    hpo_ids = hpo_result.get("hpo_ids", [])

    # ── Step 4: Graph retrieval ───────────────────────────────────────────────
    graph_candidates = []
    if hpo_ids:
        graph_candidates = get_top_candidates(hpo_ids, top_n=5)

    # ── Step 5: Vector retrieval ──────────────────────────────────────────────
    vector_chunks = []
    vector_context = ""
    if all_symptoms:
        vector_chunks = search_books_multi_query(all_symptoms, top_k=5)
        vector_context = format_chunks_for_prompt(vector_chunks)

    # ── Step 6: User profile ──────────────────────────────────────────────────
    user_profile = get_user_profile(user_id)

    return {
        "new_symptoms":           new_symptoms,
        "all_symptoms":           all_symptoms,
        "hpo_ids":                hpo_ids,
        "graph_candidates":       graph_candidates,
        "vector_chunks":          vector_chunks,
        "vector_context":         vector_context,
        "user_profile":           user_profile,
        "conversation_history":   history,
        "file_analysis":          file_analysis,
        "extraction_detail": {
            "duration_notes":  extraction.get("duration_notes", ""),
            "severity_notes":  extraction.get("severity_notes", ""),
            "negations":       extraction.get("raw_negations", [])
        }
    }


def _merge_symptoms(prior: list[str], new: list[str]) -> list[str]:
    """
    Merge symptom lists, deduplicate by normalized lowercase.
    Preserves original casing of first occurrence.
    """
    seen = {s.lower() for s in prior}
    merged = list(prior)
    for s in new:
        if s.lower() not in seen:
            seen.add(s.lower())
            merged.append(s)
    return merged


def format_user_profile(profile: dict | None) -> str:
    """Format user profile into a concise string for Claude's system prompt."""
    if not profile:
        return "User profile: not available"

    parts = []
    if profile.get("age"):
        parts.append(f"Age: {profile['age']}")
    if profile.get("sex"):
        parts.append(f"Sex: {profile['sex']}")
    if profile.get("blood_type"):
        parts.append(f"Blood type: {profile['blood_type']}")
    if profile.get("chronic_conditions"):
        parts.append(f"Conditions: {', '.join(profile['chronic_conditions'])}")
    if profile.get("current_medications"):
        parts.append(f"Medications: {', '.join(profile['current_medications'])}")
    if profile.get("allergies"):
        parts.append(f"Allergies: {', '.join(profile['allergies'])}")

    return "User profile: " + " | ".join(parts) if parts else "User profile: not available"


def format_graph_candidates(candidates: list[dict]) -> str:
    """Format graph candidates into a concise string for Claude's prompt."""
    if not candidates:
        return "No graph candidates found."

    lines = ["Knowledge graph candidates (ranked by symptom match):"]
    for i, c in enumerate(candidates, 1):
        matched = ", ".join(c.get("matched_names", []))
        ratio = c.get("match_ratio", 0)
        drugs = ", ".join(c.get("drugs", [])[:3]) or "none listed"
        lines.append(
            f"  {i}. {c['disease']} "
            f"(matched: {matched} | ratio: {ratio} | drugs: {drugs})"
        )
    return "\n".join(lines)