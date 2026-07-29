import os
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

DATA_DIR = BASE_DIR / "data"
USER_DATA_DIR = DATA_DIR / "users"
REFERENCE_DATA_DIR = DATA_DIR / "reference"
TEMPLATES_DIR = BASE_DIR / "templates"
PUBLIC_DIR = BASE_DIR / "public"


def riot_api_key() -> str:
    return os.getenv("RIOT_API_KEY", "").strip()
