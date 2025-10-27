#!/bin/bash
cd "$(dirname "$0")"
source .venv/bin/activate
export PATH="/opt/homebrew/opt/postgresql@15/bin:$PATH"

echo "Starting PostgreSQL and Redis..."
brew services start postgresql@15
brew services start redis

echo "Starting Backend API..."
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
