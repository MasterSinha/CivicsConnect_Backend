from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    database_url: str
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60
    jwt_remember_me_expire_days: int = 30
    frontend_origins: str = "http://localhost:5173,http://localhost:3000,http://localhost:8000,http://localhost:5174,http://127.0.0.1:3000,http://127.0.0.1:8000,http://10.10.53.122:8000,http://10.10.53.122:3000,https://civicscon.web.app,https://civicsconnect-frontend-134081639696.asia-south1.run.app"
    frontend_origin: str = ""
    environment: str = "development"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-1.5-flash"
    cookie_samesite: str = "lax"
    upload_storage: str = "local"
    gcp_storage_bucket: str = ""
    gcp_project_id: str = ""
    gcs_bucket_name: str = ""
    gcs_public_base_url: str = ""

    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", env_file_encoding="utf-8")

    @property
    def secure_cookies(self) -> bool:
        return self.environment.lower() == "production"

    @property
    def cors_origins(self) -> list[str]:
        raw_origins = self.frontend_origins
        if self.frontend_origin:
            raw_origins += f",{self.frontend_origin}"
        origins = [origin.strip() for origin in raw_origins.split(",") if origin.strip()]
        return origins

    @property
    def storage_bucket_name(self) -> str:
        return self.gcp_storage_bucket or self.gcs_bucket_name

    @property
    def storage_project_id(self) -> str | None:
        return self.gcp_project_id or None


@lru_cache
def get_settings() -> Settings:
    return Settings()
