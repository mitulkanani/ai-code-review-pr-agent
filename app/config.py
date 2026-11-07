from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
    review_provider: str = os.getenv("REVIEW_PROVIDER", "rules").strip().lower()
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    api_key: str = os.getenv("API_KEY", "")
    database_path: str = os.getenv("DATABASE_PATH", "data/reviews.db")
    max_files_per_review: int = int(os.getenv("MAX_FILES_PER_REVIEW", "100"))
    max_patch_chars: int = int(os.getenv("MAX_PATCH_CHARS", "120000"))


settings = Settings()
