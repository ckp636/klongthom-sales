from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/.env locally; on Vercel the same names come from project env vars.
_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # No defaults for credentials — they must come from the environment.
    DB_HOST: str
    DB_PORT: int = 1433
    DB_USER: str
    DB_PASSWORD: str
    DB_NAME: str
    # Azure SQL requires TDS 7.4 (encrypted login). 7.0 cannot connect.
    DB_TDS_VERSION: str = "7.4"

    API_PREFIX: str = "/api"
    CORS_ORIGINS: list[str] = ["*"]

    # POST /api/auth/login-dev logs in without LINE. Keep false in production.
    DEV_LOGIN_ENABLED: bool = False

    # HMAC key for store QR codes. When set, every submission must carry a
    # valid qrSig for its store; when empty, QR signatures are not checked.
    QR_HMAC_SECRET: str = ""


settings = Settings()
