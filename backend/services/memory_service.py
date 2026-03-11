from supabase import create_client
from config import settings
import uuid

from dotenv import load_dotenv
import os

load_dotenv()  

# Backend always uses service key — RLS is for client-side protection only
# supabase = create_client(settings.supabase_url, settings.supabase_key)
supabase = create_client(settings.supabase_url, settings.supabase_service_key)



def create_session(user_id: str) -> str:
    result = supabase.table("sessions").insert({
        "user_id": user_id,
        "status": "active"
    }).execute()
    return result.data[0]["session_id"]


def save_message(session_id: str, role: str,
                 content: str,
                 symptoms: list = None, 
                 hpo_terms: list = None,
                 input_method: str = "text"):
    supabase.table("messages").insert({
        "session_id": session_id,
        "role": role,
        "content": content,
        "extracted_symptoms": symptoms or [],
        "hpo_terms": hpo_terms or [],
        "input_method":  input_method
    }).execute()


def get_history(session_id: str) -> list:
    result = supabase.table("messages") \
        .select("role, content") \
        .eq("session_id", session_id) \
        .order("created_at") \
        .execute()
    return result.data  # [{"role": "user", "content": "..."}, ...]


def get_user_profile(user_id: str) -> dict | None:
    result = supabase.table("user_profiles") \
        .select("*") \
        .eq("user_id", user_id) \
        .execute()
    return result.data[0] if result.data else None


def conclude_session(session_id: str, diagnoses: list):
    supabase.table("sessions").update({
        "status": "concluded",
        "final_diagnoses": diagnoses
    }).eq("session_id", session_id).execute()