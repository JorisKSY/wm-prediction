# config.py

import os
from pathlib import Path
from dotenv import load_dotenv

# .env liegt im gleichen Ordner wie diese config.py
ENV_PATH = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=ENV_PATH)


# LLM / HAW Endpoint
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "qwen2.5-7b")

# NewsAPI
NEWS_API_KEY = os.getenv("NEWS_API_KEY")

# SportMonks
SPORTMONKS_API_KEY = os.getenv("SPORTMONKS_API_KEY")


def check_required_keys():
    required_keys = {
        "OPENAI_API_KEY": OPENAI_API_KEY,
        "NEWS_API_KEY": NEWS_API_KEY,
        "SPORTMONKS_API_KEY": SPORTMONKS_API_KEY,
    }

    missing = [name for name, value in required_keys.items() if not value]

    if missing:
        raise ValueError(
            f"Missing required environment variables: {', '.join(missing)}"
        )


check_required_keys()