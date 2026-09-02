from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )

    DB_HOST: str
    DB_PORT: int = 1433
    DB_USER: str
    DB_PASSWORD: str
    DB_NAME: str = "KlongthomSales"
    DB_DRIVER: str = "ODBC Driver 18 for SQL Server"

    API_PREFIX: str = "/api"
    CORS_ORIGINS: list[str] = ["*"]


settings = Settings()
