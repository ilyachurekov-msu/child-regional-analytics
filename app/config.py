from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "postgresql+psycopg://regional:regional@localhost:5432/regional"
    api_url: str = "http://localhost:8000"
    raw_dir: str = "data/archive"
    core_managed_externally: bool = False
    stat_updates_enabled: bool = False
    stat_update_interval: int = 86400


@lru_cache
def settings():
    return Settings()
