"""Export the real application's schema without starting its lifespan or a DB."""

import json
import os
import sys
from pathlib import Path

# Deterministic public routes, independent of a developer's .env and live DB.
os.environ.update(
    DATABASE_URL="sqlite://", APP_ENV="production",
    SECRET_KEY="openapi-schema-only-not-for-auth",  # noqa: S106 - no authentication or lifespan runs
    ATELIER_TEST_CLOCK_ENABLED="false", OPENAI_API_KEY="",
)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import create_app  # noqa: E402

if __name__ == "__main__":
    print(json.dumps(create_app().openapi(), sort_keys=True, ensure_ascii=False))
