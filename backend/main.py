import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from config import settings
from routers import chat, consultation, profile


os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_API_KEY"] = settings.langchain_api_key
os.environ["LANGCHAIN_PROJECT"] = settings.langchain_project


app = FastAPI(title="MurphyBot API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten before production
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router, prefix="/chat", tags=["chat"])
app.include_router(consultation.router, prefix="/consultation", tags=["consultation"])
app.include_router(profile.router, prefix="/profile", tags=["profile"])

@app.get("/health")
def health():
    return {"status": "ok"}