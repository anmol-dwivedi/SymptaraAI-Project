"""
memory_service.py
=================
All Supabase CRUD operations.

Stores location, timezone, and local time on session conclusion
so the medical report has full patient context.
"""

from supabase import create_client
from config import settings
from dotenv import load_dotenv

load_dotenv()

supabase = create_client(settings.supabase_url, settings.supabase_service_key)


def create_session(user_id: str) -> str:
    result = supabase.table("sessions").insert({
        "user_id": user_id,
        "status":  "active"
    }).execute()
    return result.data[0]["session_id"]


def save_message(
    session_id:   str,
    role:         str,
    content:      str,
    symptoms:     list = None,
    hpo_terms:    list = None,
    input_method: str  = "text"
):
    supabase.table("messages").insert({
        "session_id":         session_id,
        "role":               role,
        "content":            content,
        "extracted_symptoms": symptoms or [],
        "hpo_terms":          hpo_terms or [],
        "input_method":       input_method
    }).execute()


def get_history(session_id: str) -> list:
    result = supabase.table("messages") \
        .select("role, content") \
        .eq("session_id", session_id) \
        .order("created_at") \
        .execute()
    return result.data


def get_user_profile(user_id: str) -> dict | None:
    result = supabase.table("user_profiles") \
        .select("*") \
        .eq("user_id", user_id) \
        .execute()
    return result.data[0] if result.data else None


def conclude_session(
    session_id:      str,
    diagnoses:       list,
    mcp_enrichment:  dict = None,
    location:        dict = None,
    timezone:        str  = None,
    local_time:      str  = None
):
    """
    Mark session as concluded.
    Stores diagnoses, MCP enrichment, and patient location/time context
    so the medical report has full fidelity.

    Args:
        location:   {"lat": float, "lng": float, "location_text": str}
        timezone:   IANA timezone string e.g. "America/Chicago"
        local_time: ISO string from patient's browser e.g. "2026-03-13T15:45:00"
    """
    update = {
        "status":          "concluded",
        "final_diagnoses": diagnoses
    }
    if mcp_enrichment:  update["mcp_enrichment"]      = mcp_enrichment
    if location:        update["location"]             = location
    if timezone:        update["timezone"]             = timezone
    if local_time:      update["concluded_at_local"]   = local_time

    supabase.table("sessions").update(update) \
        .eq("session_id", session_id).execute()


def get_session_conclusion(session_id: str) -> dict:
    """
    Retrieve stored conclusion data for POST_CONCLUSION context.
    Includes MCP enrichment, location, and timezone.
    """
    result = supabase.table("sessions") \
        .select("final_diagnoses, mcp_enrichment, status, location, timezone, concluded_at_local") \
        .eq("session_id", session_id) \
        .execute()
    return result.data[0] if result.data else {}


def get_session_files(session_id: str) -> list[str]:
    """
    Return all Claude analyses for files uploaded in this session.
    Called by context_assembler on every turn — persistent file context.
    """
    try:
        result = supabase.table("session_files") \
            .select("claude_analysis") \
            .eq("session_id", session_id) \
            .execute()
        return [
            row["claude_analysis"]
            for row in result.data
            if row.get("claude_analysis")
        ]
    except Exception:
        return []


def reset_session(session_id: str):
    """Mark session as reset — called by New Session button."""
    supabase.table("sessions").update({
        "status": "reset"
    }).eq("session_id", session_id).execute()