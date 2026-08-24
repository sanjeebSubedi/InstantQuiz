from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = Path(__file__).resolve().parents[4] / ".env"


class Config(BaseSettings):
    EMAIL: str
    GEMINI_API_KEY: str
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_COLLECTION_PREFIX: str = "quiz_app"
    OPENROUTER_API_KEY: str
    DEFAULT_DIFFICULTY: str = "medium"
    DEFAULT_QUESTION_COUNT: int = 10
    QUIZ_DB_PATH: str = str(Path(__file__).resolve().parents[4] / "quiz.db")
    CORS_ORIGINS: str = "http://localhost:5173"

    model_config = SettingsConfigDict(
        env_file=_ENV_FILE, extra="ignore"
    )

    @field_validator("QDRANT_URL")
    @classmethod
    def _fill_qdrant_default(cls, value):
        return value or "http://localhost:6333"

    @property
    def cors_origin_list(self):
        """Parse the comma-separated ``CORS_ORIGINS`` string into a list."""
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


config = Config()