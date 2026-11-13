from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite+aiosqlite:////data/app.db"
    # Разрешить мониторам ходить в приватные сети (10/8, 172.16/12, 192.168/16, fc00::/7).
    allow_private_targets: bool = False


settings = Settings()
