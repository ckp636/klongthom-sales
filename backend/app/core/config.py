from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )

    DB_HOST: str = "209.15.116.56"
    DB_PORT: int = 1433
    DB_USER: str = "JCAT"
    DB_PASSWORD: str = "SKIN7646"
    DB_NAME: str = "@KlongThom_Sales"

    API_PREFIX: str = "/api"
    CORS_ORIGINS: list[str] = ["*"]


settings = Settings()
