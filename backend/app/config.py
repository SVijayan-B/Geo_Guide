from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

APP_NAME = os.getenv("APP_NAME", "AURA Travel AI")
DEBUG = os.getenv("DEBUG", "true").strip().lower() in {"1", "true", "yes", "on"}
