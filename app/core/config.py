from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    APP_NAME: str = "Toko Web Jaya"
    APP_ENV: str = "development"
    SECRET_KEY: str = "change-this"
    BASE_URL: str = "http://localhost:8000"

    DATABASE_URL: str
    REDIS_URL: str = "redis://localhost:6379/0"

    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/auth/google/callback"

    SMTP_HOST: str = "smtp.sumopod.com"
    SMTP_PORT: int = 465
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "noreply@dev-tokowebjaya.roc.web.id"
    EMAIL_FROM: str = "Toko Web Jaya <noreply@dev-tokowebjaya.roc.web.id>"

    UPLOAD_DIR: str = "static/uploads"
    MAX_UPLOAD_SIZE_MB: int = 100

    DUITKU_MERCHANT_CODE: str = ""
    DUITKU_API_KEY: str = ""
    DUITKU_CALLBACK_URL: str = ""
    DUITKU_BASE_URL: str = "https://sandbox.duitku.com/webapi/api"

    MAYAR_API_KEY: str = ""
    MAYAR_CALLBACK_URL: str = ""
    MAYAR_BASE_URL: str = "https://api.mayar.id"

    SUPPORTED_LOCALES: list[str] = ["id", "en"]
    DEFAULT_LOCALE: str = "id"

    # Currency & tax
    SUPPORTED_CURRENCIES: list[str] = ["IDR", "USD"]
    DEFAULT_CURRENCY: str = "IDR"
    USD_TO_IDR_RATE: float = 16000.0     # Fallback rate; update via task or .env
    VAT_RATE_IDR: float = 0.11           # 11% PPN Indonesia
    VAT_RATE_USD: float = 0.0            # No VAT for USD by default

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
