from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    EMAIL: str
    GEMINI_API_KEY: str
    QDRANT_URL: str

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


config = Config()
