import os
from functools import lru_cache
from dotenv import load_dotenv
from pydantic import BaseModel

load_dotenv()


class Settings(BaseModel):
    anthropic_api_key: str = ""
    scorecard_db_path: str = "scorecard.sqlite"


class ConfigurationError(Exception):
    """Raised when a required piece of runtime configuration is missing."""


@lru_cache
def get_settings() -> Settings:
    return Settings(
        anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
        scorecard_db_path=os.environ.get("SCORECARD_DB_PATH", "scorecard.sqlite"),
    )


def require_anthropic_api_key(settings: Settings) -> str:
    """Fail with a clear message rather than letting the Anthropic SDK raise its
    own less obvious error deep inside the call stack."""
    if not (settings.anthropic_api_key or "").strip():
        raise ConfigurationError("ANTHROPIC_API_KEY is not configured")
    return settings.anthropic_api_key
