from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite+aiosqlite:///./kvitto.db"
    webhook_secret: str = "dev-secret"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
