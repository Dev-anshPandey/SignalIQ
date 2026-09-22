import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

class Settings:
    PROJECT_NAME: str = "SignalIQ"
    BASE_DIR: Path = BASE_DIR
    DATA_DIR: Path = BASE_DIR / "app" / "data"
    
    LLM_BASE_URL: str = os.getenv("LLM_BASE_URL", "http://localhost:11434").rstrip("/")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "llama3.2:1b")
    LLM_TIMEOUT_SECONDS: float = float(os.getenv("LLM_TIMEOUT_SECONDS", "45.0"))
    
    APP_HOST: str = os.getenv("APP_HOST", "0.0.0.0")
    APP_PORT: int = int(os.getenv("APP_PORT", "8000"))
    
    # Reference date for recency calculations (Local execution context: September 2026)
    REFERENCE_DATE: str = "2026-09-21"

settings = Settings()
