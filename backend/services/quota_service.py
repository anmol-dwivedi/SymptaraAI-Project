from datetime import datetime, timezone, timedelta
from config import settings
from supabase import create_client

supabase    = create_client(settings.supabase_url, settings.supabase_service_key)
DAILY_LIMIT = 5


def _parse_timestamp(ts: str) -> datetime:
    """
    Parse ISO timestamp from Supabase safely on Python 3.10.
    Python 3.10's fromisoformat() chokes on timezone offsets like
    '2026-03-28T03:47:55.23687+00:00' — this handles all variants.
    """
    if not ts:
        return datetime.now(timezone.utc)
    # Replace Z with +00:00 for consistency
    ts = ts.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(ts)
    except ValueError:
        # Strip microseconds + offset, treat as UTC
        ts_clean = ts[:19]
        return datetime.fromisoformat(ts_clean).replace(tzinfo=timezone.utc)


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
            "user_id":       user_id,
            "sessions_used": 1,
            "window_start":  now.isoformat()
        }).execute()
        return {"allowed": True, "sessions_used": 1, "limit": DAILY_LIMIT}

    quota        = res.data[0]
    window_start = _parse_timestamp(quota["window_start"])

    # Ensure window_start is timezone-aware for comparison
    if window_start.tzinfo is None:
        window_start = window_start.replace(tzinfo=timezone.utc)

    # Reset if 24hr window has passed
    if now - window_start > timedelta(hours=24):
        supabase.table("user_quotas").update({
            "sessions_used": 1,
            "window_start":  now.isoformat()
        }).eq("user_id", user_id).execute()
        return {"allowed": True, "sessions_used": 1, "limit": DAILY_LIMIT}

    if quota["sessions_used"] >= DAILY_LIMIT:
        reset_at = window_start + timedelta(hours=24)
        return {
            "allowed":       False,
            "sessions_used": quota["sessions_used"],
            "limit":         DAILY_LIMIT,
            "reset_at":      reset_at.isoformat()
        }

    supabase.table("user_quotas").update({
        "sessions_used": quota["sessions_used"] + 1
    }).eq("user_id", user_id).execute()

    return {
        "allowed":       True,
        "sessions_used": quota["sessions_used"] + 1,
        "limit":         DAILY_LIMIT
    }