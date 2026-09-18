from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    redis_url: str
    google_model: str = "gemini-3.6-flash"
    mcp_agent_key: str = ""
    langcache_host: str = ""
    langcache_cache_id: str = ""
    langcache_api_key: str = ""
    agent_memory_base_url: str
    agent_memory_store_id: str
    agent_memory_api_key: str
    agent_memory_namespace: str = "value-travel"
    embedding_model: str = "redis/langcache-embed-v3-small"
    studio_sqlserver_host: str = "value-travel-sqlserver"
    studio_sqlserver_port: int = 1433
    studio_sqlserver_user: str = "value_travel_editor"
    studio_sqlserver_password: str = ""

    @property
    def memory_configured(self):
        return True

    @property
    def langcache_configured(self):
        return bool(
            self.langcache_host and self.langcache_cache_id and self.langcache_api_key
        )

    redis_namespace: str = "value-travel"
    effective_app_name: str = "value-travel"
    agent_memory_http_keepalive_seconds: int = 300
    agent_memory_similarity_threshold: float = 0.25
    langcache_http_keepalive_seconds: int = 300
    langcache_similarity_threshold: float = 0.9

    @property
    def effective_agent_memory_namespace(self):
        return self.agent_memory_namespace


@lru_cache
def get_settings():
    return Settings()
