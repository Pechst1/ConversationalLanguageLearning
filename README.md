# Conversational Language Learning Backend

This repository contains the backend implementation for the Conversational Language Learning application. The service is designed following the technical roadmap and product specification provided in the project wiki. It delivers a FastAPI-based API, PostgreSQL persistence layer, Celery/Redis background processing, and integrations with LLM providers for conversational experiences.

## Getting Started

### Prerequisites

- Python 3.11+
- PostgreSQL 15+
- Redis 7+
- (Optional) Docker and Docker Compose for containerized setup

### Installation

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
cp .env.example .env
```

Update `.env` with your secrets and infrastructure endpoints.

#### LLM Configuration

Set the provider credentials and preferred models to unlock the conversational features. The
service supports automatic fallback between OpenAI and Anthropic compatible APIs.

```
OPENAI_API_KEY="sk-..."
ANTHROPIC_API_KEY="anthropic-..."  # optional fallback
PRIMARY_LLM_PROVIDER=openai
SECONDARY_LLM_PROVIDER=anthropic
OPENAI_MODEL=gpt-4o-mini
ANTHROPIC_MODEL=claude-3-5-sonnet
```

You can also override the API base URLs for self-hosted compatible gateways by setting
`OPENAI_API_BASE` or `ANTHROPIC_API_BASE`. Timeout and retry behaviour is controlled via
`LLM_REQUEST_TIMEOUT_SECONDS` and `LLM_MAX_RETRIES`.

### Database Migrations

The project uses Alembic for migrations.

```bash
alembic upgrade head
```

To create a new migration after modifying models:

```bash
alembic revision --autogenerate -m "description"
```

### Vocabulary Seed Script

Generate a sample CSV and seed the vocabulary table:

```bash
python scripts/seed_vocabulary.py --generate-sample
python scripts/seed_vocabulary.py --csv vocabulary_fr_sample.csv
```

### Progress & Review API

The SRS module powers the learner progress endpoints exposed under `/api/v1/progress`:

- `GET /api/v1/progress/queue` – retrieve due and new vocabulary items for the learner's next session.
- `POST /api/v1/progress/review` – submit a rating (0-3) after reviewing a word to receive the next scheduled review time.
- `GET /api/v1/progress/{word_id}` – inspect the stored stability, difficulty, and repetition counters for a specific word.

## Project Structure

```
app/
  api/                # API routers (FastAPI)
  core/               # Core domain logic (SRS, conversation engine, etc.)
  db/                 # Database models, sessions, and migrations
  schemas/            # Pydantic models
  services/           # Business services
  tasks/              # Celery tasks
  utils/              # Utility helpers
scripts/              # CLI utilities (e.g., seeders)
alembic/              # Migration environment and versions
```

## Next Steps

- Integrate the conversation generation pipeline backed by LLM providers.
- Implement the full FSRS algorithm tuning and expose progress analytics dashboards.
- Expand automated testing and continuous integration workflows.

Refer to the [project wiki](https://github.com/Pechst1/ConversationalLanguageLearning/wiki) for the comprehensive roadmap.
