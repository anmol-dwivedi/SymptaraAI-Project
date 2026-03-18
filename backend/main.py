import os
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from config import settings
from routers import consultation, profile

logging.basicConfig(level=logging.INFO)

os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_API_KEY"]    = settings.langchain_api_key
os.environ["LANGCHAIN_PROJECT"]    = settings.langchain_project

app = FastAPI(title="Symptara API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # tighten to Lovable URL before production
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(consultation.router, prefix="/consultation", tags=["consultation"])
app.include_router(profile.router,      prefix="/profile",      tags=["profile"])


@app.get("/health")
def health():
    return {"status": "ok", "version": "2.0.0"}