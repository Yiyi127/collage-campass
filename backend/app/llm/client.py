# backend/app/llm/client.py
import anthropic
from app.config import get_settings


def get_client() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=get_settings().anthropic_api_key)
