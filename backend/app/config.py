import os
from dotenv import load_dotenv
from pydantic_settings import BaseSettings

load_dotenv()

class Settings(BaseSettings):
    amap_api_key: str = os.getenv("AMAP_API_KEY", "your_amap_key_here")
    llm_model_id: str = os.getenv("LLM_MODEL_ID", "gpt-4")
    llm_api_key: str = os.getenv("LLM_API_KEY", "")
    llm_base_url: str = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")

def get_settings():
    return Settings()
