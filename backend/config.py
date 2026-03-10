from pydantic_settings import BaseSettings
from dotenv import load_dotenv
import os

load_dotenv() # to load the env variables from root dir


class Settings(BaseSettings):
    anthropic_api_key: str
    openai_api_key: str
    neo4j_uri: str
    neo4j_user: str
    neo4j_password: str
    supabase_url: str
    supabase_key: str
    supabase_service_key: str = ""
    langchain_api_key: str
    langchain_project: str = "murphybot"
    chroma_path: str = "./chroma_db"
    md_folder: str = "./docling_output"
    

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()