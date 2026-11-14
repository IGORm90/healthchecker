from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # env_ignore_empty: пустая строка из .env.example означает «не задано».
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", env_ignore_empty=True)

    database_url: str = "sqlite+aiosqlite:////data/app.db"
    # Разрешить мониторам ходить в приватные сети (10/8, 172.16/12, 192.168/16, fc00::/7).
    allow_private_targets: bool = False

    # Вход через Telegram OpenID Connect: Client ID — это ID бота из @BotFather.
    telegram_client_id: str = ""
    telegram_client_secret: str = ""
    # Должен побайтово совпадать с адресом, зарегистрированным в @BotFather.
    telegram_redirect_uri: str = ""
    # Telegram ID Пользователя, который при входе получает права Суперадмина.
    superadmin_telegram_id: int | None = None
    # Идентификатор сборки образа: Сессии другой сборки недействительны.
    build_id: str = "dev"


settings = Settings()
