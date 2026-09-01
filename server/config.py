from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    bot_token: str = ""
    bot_username: str = ""
    bot_client_id: str = ""
    # auto | webhook | polling | off
    #   auto → webhook when running in production behind a public https URL,
    #          long polling otherwise (local dev).
    bot_mode: str = "auto"
    webapp_url: str = "http://localhost:5173"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    dev_mode: bool = True
    cors_origins: str = "*"
    data_dir: str = "data"
    session_secret: str = ""


settings = Settings()
