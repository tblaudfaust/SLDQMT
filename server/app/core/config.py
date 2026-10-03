from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

SERVER_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=SERVER_DIR / ".env", extra="ignore")

    ENVIRONMENT: str = "development"
    API_V1_PREFIX: str = "/api/v1"
    # Folder holding the downloadable user manual and tablet APK (served to signed-in users only)
    RESOURCES_DIR: str = str((SERVER_DIR.parent / "downloads").as_posix())

    # Dev default: a SQLite file next to the server package, whatever the working directory.
    DATABASE_URL: str = f"sqlite:///{(SERVER_DIR / 'fieldmonitor.db').as_posix()}"

    JWT_SECRET_KEY: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    BACKEND_CORS_ORIGINS: list[str] = ["http://localhost:5173"]

    BOOTSTRAP_ADMIN_USERNAME: str = "admin"
    BOOTSTRAP_ADMIN_PASSWORD: str = "change-me-immediately"

    MAX_FAILED_LOGIN_ATTEMPTS: int = 5
    LOCKOUT_MINUTES: int = 15

    SYNC_BATCH_MAX: int = 200
    REPORT_DIR: str = "./reports"


settings = Settings()
