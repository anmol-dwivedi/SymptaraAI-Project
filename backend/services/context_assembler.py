"""
context_assembler.py
====================
Full hybrid RAG pipeline. Called once per user turn.

Adds location_text and local_time to context so triage prompts
can reason about patient location and symptom onset timing.
"""

from services.symptom_extractor import extract_symptoms, get_all_positive_symptoms
from services.hpo_mapper import map_symptoms_to_hpo
from services.graph_service import get_top_candidates
from services.vector_service import search_books_multi_query, format_chunks_for_prompt
from services.memory_service import get_history, get_user_profile, get_session_files


def assemble_context(
    user_message:         str,
    session_id:           str,
    user_id:              str,
    accumulated_symptoms: list[str] = None,
    file_analysis:        str = None,
    location_text:        str = None,
    local_time:           str = None,
    timezone:             str = None
) -> dict:
    """
    Full hybrid RAG pipeline.

    New params:
        location_text: human-readable location e.g. "Dallas, TX"
        local_time:    ISO datetime from browser e.g. "2026-03-13T15:45:00"
        timezone:      IANA timezone e.g. "America/Chicago"
    """
    # ── Step 1: Extract symptoms ──────────────────────────────────────────────
    history      = get_history(session_id)
    extraction   = extract_symptoms(user_message, conversation_history=history)
    new_symptoms = get_all_positive_symptoms(extraction)

    # ── Step 2: Merge symptoms ────────────────────────────────────────────────
    prior        = accumulated_symptoms or []
    all_symptoms = _merge_symptoms(prior, new_symptoms)

    # ── Step 3: HPO mapping ───────────────────────────────────────────────────
    hpo_result = map_symptoms_to_hpo(all_symptoms) if all_symptoms else {}
    hpo_ids    = hpo_result.get("hpo_ids", [])

    # ── Step 4: Graph retrieval ───────────────────────────────────────────────
    graph_candidates = []
    if hpo_ids:
        graph_candidates = get_top_candidates(hpo_ids, top_n=5)

    # ── Step 5: Vector retrieval ──────────────────────────────────────────────
    vector_chunks  = []
    vector_context = ""
    if all_symptoms:
        vector_chunks  = search_books_multi_query(all_symptoms, top_k=5)
        vector_context = format_chunks_for_prompt(vector_chunks)

    # ── Step 6: User profile ──────────────────────────────────────────────────
    user_profile = get_user_profile(user_id)

    # ── Step 7: Session file analyses (persistent across all turns) ───────────
    session_file_analyses = get_session_files(session_id)
    all_file_analyses     = []
    if session_file_analyses:
        all_file_analyses.extend(session_file_analyses)
    if file_analysis and file_analysis not in all_file_analyses:
        all_file_analyses.append(file_analysis)
    combined_file_analysis = "\n\n---\n\n".join(all_file_analyses) if all_file_analyses else None

    return {
        "new_symptoms":         new_symptoms,
        "all_symptoms":         all_symptoms,
        "hpo_ids":              hpo_ids,
        "graph_candidates":     graph_candidates,
        "vector_chunks":        vector_chunks,
        "vector_context":       vector_context,
        "user_profile":         user_profile,
        "conversation_history": history,
        "file_analysis":        combined_file_analysis,
        "location_text":        location_text,
        "local_time":           local_time,
        "timezone":             timezone,
        "extraction_detail": {
            "duration_notes": extraction.get("duration_notes", ""),
            "severity_notes": extraction.get("severity_notes", ""),
            "negations":      extraction.get("raw_negations", [])
        }
    }


def _merge_symptoms(prior: list[str], new: list[str]) -> list[str]:
    seen   = {s.lower() for s in prior}
    merged = list(prior)
    for s in new:
        if s.lower() not in seen:
            seen.add(s.lower())
            merged.append(s)
    return merged


def format_user_profile(profile: dict | None) -> str:
    if not profile:
        return "User profile: not available"
    parts = []
    if profile.get("age"):            parts.append(f"Age: {profile['age']}")
    if profile.get("sex"):            parts.append(f"Sex: {profile['sex']}")
    if profile.get("blood_type"):     parts.append(f"Blood type: {profile['blood_type']}")
    if profile.get("chronic_conditions"):
        parts.append(f"Conditions: {', '.join(profile['chronic_conditions'])}")
    if profile.get("current_medications"):
        parts.append(f"Medications: {', '.join(profile['current_medications'])}")
    if profile.get("allergies"):
        parts.append(f"Allergies: {', '.join(profile['allergies'])}")
    return "User profile: " + " | ".join(parts) if parts else "User profile: not available"


def format_graph_candidates(candidates: list[dict]) -> str:
    if not candidates:
        return "No graph candidates found."
    lines = ["Knowledge graph candidates (ranked by symptom match):"]
    for i, c in enumerate(candidates, 1):
        matched = ", ".join(c.get("matched_names", []))
        ratio   = c.get("match_ratio", 0)
        drugs   = ", ".join(c.get("drugs", [])[:3]) or "none listed"
        lines.append(
            f"  {i}. {c['disease']} "
            f"(matched: {matched} | ratio: {ratio} | drugs: {drugs})"
        )
    return "\n".join(lines)