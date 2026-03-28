from datetime import datetime, timezone, timedelta
# from backend.config import settings
from config import settings
from supabase import create_client

supabase = create_client(settings.supabase_url, settings.supabase_service_key)

DAILY_LIMIT = 5

def is_admin(user_id: str) -> bool:
    res = supabase.table("admin_users").select("user_id").eq("user_id", user_id).execute()
    return len(res.data) > 0

def check_and_increment_quota(user_id: str) -> dict:
    """Returns {"allowed": bool, "sessions_used": int, "limit": int}"""
    if is_admin(user_id):
        return {"allowed": True, "sessions_used": -1, "limit": -1}

    now = datetime.now(timezone.utc)
    res = supabase.table("user_quotas").select("*").eq("user_id", user_id).execute()

    if not res.data:
        # First session ever
        supabase.table("user_quotas").insert({
            "user_id": user_id,
            "sessions_used": 1,
            "window_start": now.isoformat()
        }).execute()
        return {"allowed": True, "sessions_used": 1, "limit": DAILY_LIMIT}

    quota = res.data[0]
    window_start = datetime.fromisoformat(quota["window_start"])

    # Reset if 24hr window has passed
    if now - window_start > timedelta(hours=24):
        supabase.table("user_quotas").update({
            "sessions_used": 1,
            "window_start": now.isoformat()
        }).eq("user_id", user_id).execute()
        return {"allowed": True, "sessions_used": 1, "limit": DAILY_LIMIT}

    if quota["sessions_used"] >= DAILY_LIMIT:
        reset_at = window_start + timedelta(hours=24)
        return {
            "allowed": False,
            "sessions_used": quota["sessions_used"],
            "limit": DAILY_LIMIT,
            "reset_at": reset_at.isoformat()
        }

    supabase.table("user_quotas").update({
        "sessions_used": quota["sessions_used"] + 1
    }).eq("user_id", user_id).execute()

    return {
        "allowed": True,
        "sessions_used": quota["sessions_used"] + 1,
        "limit": DAILY_LIMIT
    }