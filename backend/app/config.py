import os
from functools import lru_cache
from pydantic import BaseModel


class Settings(BaseModel):
    anthropic_api_key: str = ""
    scorecard_db_path: str = "scorecard.sqlite"


@lru_cache
def get_settings() -> Settings:
    return Settings(
        anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
        scorecard_db_path=os.environ.get("SCORECARD_DB_PATH", "scorecard.sqlite"),
    )
