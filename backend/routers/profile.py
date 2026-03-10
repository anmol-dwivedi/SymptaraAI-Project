from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from services.memory_service import supabase

from dotenv import load_dotenv
import os

load_dotenv()


router = APIRouter()

class ProfileCreate(BaseModel):
    user_id: str
    age: int | None = None
    sex: str | None = None
    blood_type: str | None = None
    allergies: list[str] = []
    chronic_conditions: list[str] = []
    current_medications: list[str] = []
    past_surgeries: list[str] = []

@router.post("/")
def create_profile(profile: ProfileCreate):
    result = supabase.table("user_profiles").upsert(profile.dict()).execute()
    return result.data[0]

@router.get("/{user_id}")
def get_profile(user_id: str):
    result = supabase.table("user_profiles").select("*").eq("user_id", user_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Profile not found")
    return result.data[0]




