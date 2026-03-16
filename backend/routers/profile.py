# from fastapi import APIRouter, HTTPException
# from pydantic import BaseModel
# from services.memory_service import supabase

# from dotenv import load_dotenv
# import os

# load_dotenv()


# router = APIRouter()

# class ProfileCreate(BaseModel):
#     user_id: str
#     age: int | None = None
#     sex: str | None = None
#     blood_type: str | None = None
#     allergies: list[str] = []
#     chronic_conditions: list[str] = []
#     current_medications: list[str] = []
#     past_surgeries: list[str] = []

# @router.post("/")
# def create_profile(profile: ProfileCreate):
#     result = supabase.table("user_profiles").upsert(profile.dict()).execute()
#     return result.data[0]

# @router.get("/{user_id}")
# def get_profile(user_id: str):
#     result = supabase.table("user_profiles").select("*").eq("user_id", user_id).execute()
#     if not result.data:
#         raise HTTPException(status_code=404, detail="Profile not found")
#     return result.data[0]




from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from services.memory_service import supabase

router = APIRouter()

class ProfileCreate(BaseModel):
    user_id: str
    age: Optional[int] = None
    sex: Optional[str] = None
    blood_type: Optional[str] = None
    allergies: list[str] = []
    chronic_conditions: list[str] = []
    current_medications: list[str] = []
    past_surgeries: list[str] = []

@router.post("/")
def save_profile(profile: ProfileCreate):
    # Build payload — only include scalar fields that are explicitly set
    # to avoid overwriting existing data with null on partial saves
    payload = {"user_id": profile.user_id}
    if profile.age is not None:
        payload["age"] = profile.age
    if profile.sex is not None:
        payload["sex"] = profile.sex
    if profile.blood_type is not None:
        payload["blood_type"] = profile.blood_type
    # List fields: always include (empty list is a valid explicit clear)
    payload["allergies"] = profile.allergies
    payload["chronic_conditions"] = profile.chronic_conditions
    payload["current_medications"] = profile.current_medications
    payload["past_surgeries"] = profile.past_surgeries

    result = (
        supabase.table("user_profiles")
        .upsert(payload, on_conflict="user_id")
        .execute()
    )
    return result.data[0]

@router.get("/{user_id}")
def get_profile(user_id: str):
    result = (
        supabase.table("user_profiles")
        .select("*")
        .eq("user_id", user_id)
        .execute()
    )
    # Return null instead of 404 — frontend treats null as "no profile yet"
    return result.data[0] if result.data else None