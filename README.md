# Conversational Language Learning Backend

This repository contains the backend implementation for the Conversational Language Learning application. The service is designed following the technical roadmap and product specification provided in the project wiki. It delivers a FastAPI-based API, PostgreSQL persistence layer, Celery/Redis background processing, and integrations with LLM providers for conversational experiences.

## Getting Started

### Prerequisites

- Python 3.11+
- PostgreSQL 15+
- Redis 7+
- (Optional) Docker and Docker Compose for containerized setup
- spaCy French model (`fr_core_news_sm`) installed locally

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

#### Language Processing

The error detection pipeline relies on spaCy for part-of-speech tagging. Install the
French model (configurable via `FRENCH_NLP_MODEL`) after setting up the virtual
environment:

```bash
python -m spacy download fr_core_news_sm
```

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

### Real-time Session Stream

Interactive tutoring sessions exchange turn results over a WebSocket channel at
`/api/v1/sessions/{session_id}/ws`. Authenticate by providing the learner's access token
either as a `token` query parameter or via an `Authorization: Bearer <token>` header.

Upon connection the server emits a `session_ready` envelope containing the latest session
summary and currently connected user IDs. Clients can then send the following payloads:

```json
// Submit a learner turn and optional suggested vocabulary IDs
{ "type": "user_message", "content": "J'adore les baguettes!", "suggested_words": [123, 456] }

// Broadcast typing indicators to other participants
{ "type": "typing", "is_typing": true }

// Keep the connection alive and receive a server timestamp
{ "type": "heartbeat" }
```

Every accepted learner message results in a `turn_result` response that mirrors the REST
`POST /sessions/{id}/messages` payload (session overview, assistant reply, XP awarded, and
word-level feedback). Heartbeats return the server time and typing indicators are
rebroadcast to all active connections for that session.

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
