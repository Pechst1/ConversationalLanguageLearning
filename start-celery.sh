#!/bin/bash
cd "$(dirname "$0")"
source .venv/bin/activate
celery -A app.celery_app worker --loglevel=info
