from fastapi import HTTPException, Header
from supabase import create_client
from config import settings  

supabase_client = create_client(settings.supabase_url, settings.supabase_service_key)

async def get_current_user(authorization: str = Header(...)) -> str:
    """Extracts and verifies Supabase JWT, returns user_id."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid auth header")
    token = authorization.split(" ")[1]
    try:
        user = supabase_client.auth.get_user(token)
        return user.user.id
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")