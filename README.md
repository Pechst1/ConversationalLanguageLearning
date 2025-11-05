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

### Full Stack Quickstart (Docker)

To boot the entire platform locally — API, PostgreSQL, Redis, Celery worker & beat,
and the Flower monitoring dashboard — follow the sequence below from a clean clone.

```bash
# 1. Clone & enter the repository
git clone https://github.com/pechst1/ConversationalLanguageLearning.git
cd ConversationalLanguageLearning

# 2. Provision a virtual environment for local tooling (optional but recommended)
python -m venv .venv
source .venv/bin/activate

# 3. Install development dependencies (needed for Alembic, linting, etc.)
pip install -e .[dev]

# 4. Prepare environment variables
cp .env.example .env
# Edit .env and supply database passwords, JWT secrets, and LLM credentials

# 5. Download the required spaCy language model once
python -m spacy download fr_core_news_sm

# 6. Build & launch the complete stack with hot reload
docker compose -f docker/docker-compose.dev.yml up --build
```

Once all services are healthy you can access:

- API: http://localhost:8000/api/v1
- Interactive API docs (served by FastAPI): http://localhost:8000/api/v1/docs
- Flower dashboard (Celery monitoring): http://localhost:5555
- PostgreSQL: localhost:5432 (`postgres` / `postgres` by default)
- Redis: localhost:6379

Shut everything down with `Ctrl+C` or `docker compose -f docker/docker-compose.dev.yml down`.

> **PostgreSQL persistence reminder**
>
> The development Compose file mounts a named volume called `pg_data` to `/var/lib/postgresql/data`. Keep this volume between container restarts or swap it with an equivalent managed PostgreSQL instance so that learner accounts and Anki cards persist. Removing or recreating the volume resets the database and permanently deletes all users, sessions, and card progress.

#### Verify migrations & data after restarts

If you restart the stack or rebuild containers, run the following checks to confirm the schema and data survived:

1. **Re-run Alembic migrations** – this is idempotent and ensures the schema is current.

   ```bash
   docker compose -f docker/docker-compose.dev.yml exec api alembic upgrade head
   ```

2. **Inspect the `users` table** – confirm rows are still present after a restart. You can adjust the query for other tables such as `anki_cards`.

   ```bash
   docker compose -f docker/docker-compose.dev.yml exec db \
     psql -U postgres -d language_learning \
     -c "SELECT id, email, created_at FROM users ORDER BY created_at DESC LIMIT 5;"
   ```

3. **Spot-check counts** – a quick way to verify retention without dumping full rows.

   ```bash
   docker compose -f docker/docker-compose.dev.yml exec db \
     psql -U postgres -d language_learning \
     -c "SELECT COUNT(*) AS total_users FROM users;"
   ```

If any of these commands return empty results unexpectedly, ensure the `pg_data` volume still exists (`docker volume ls | grep pg_data`) or connect the API to a managed PostgreSQL database with persistent storage.

#### Smoke test the conversational flow

With the stack running you can exercise a full learner journey via `curl`. The
examples below assume you have [`jq`](https://stedolan.github.io/jq/) installed
to capture values from JSON responses.

```bash
# Register a learner profile (only required once)
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
        "email": "learner@example.com",
        "password": "ChangeMe123!",
        "full_name": "Demo Learner"
      }'

# Authenticate and store the issued JWT access token
ACCESS_TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
        "email": "learner@example.com",
        "password": "ChangeMe123!"
      }' | jq -r '.access_token')

# Start a new guided session and capture the session identifier
SESSION_ID=$(curl -s -X POST http://localhost:8000/api/v1/sessions \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
        "planned_duration_minutes": 15,
        "topic": "Ordering food",
        "conversation_style": "tutor",
        "difficulty_preference": "beginner",
        "generate_greeting": true
      }' | jq -r '.session.id')

# Send a learner utterance to receive corrective feedback and XP
curl -X POST http://localhost:8000/api/v1/sessions/${SESSION_ID}/messages \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
        "content": "Bonjour, je voudrais une baguette s'il vous plaît",
        "suggested_word_ids": []
      }' | jq '.assistant_turn.message.content, .error_feedback.summary'

# Inspect the running transcript
curl -X GET http://localhost:8000/api/v1/sessions/${SESSION_ID}/messages \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" | jq '.items[] | {sender, content}'
```

The assistant response includes vocabulary targets, awarded experience, and any
detected errors that can guide the learner's next turn. Continue sending
messages or close the session with:

```bash
curl -X PATCH http://localhost:8000/api/v1/sessions/${SESSION_ID} \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"status": "completed"}'
```

### Running with Docker

Container orchestration is provided via Compose files in the `docker/` directory.

**Local development with hot reload**

```bash
cp .env.example .env
docker compose -f docker/docker-compose.dev.yml up --build
```

The API is exposed at http://localhost:8000 and automatically reloads when you edit
source files. PostgreSQL and Redis data are stored in local Docker volumes. The
containers run Alembic migrations on startup; if you interrupt the first boot or see
database errors you can manually ensure the schema is up to date with:

```bash
docker compose -f docker/docker-compose.dev.yml run --rm api alembic upgrade head
```

**Staging environment preview**

```bash
cp .env.example .env.staging  # populate with staging secrets
docker compose -f docker/docker-compose.staging.yml up --detach
```

The staging compose file assumes you have already published a container image to the
GitHub Container Registry (`ghcr.io/pechst1/conversational-language-learning:latest`).

**Production deployment blueprint**

```bash
cp .env.example .env.prod  # populate with production secrets
docker compose -f docker/docker-compose.prod.yml pull
docker compose -f docker/docker-compose.prod.yml up -d
```

The production stack runs two API replicas behind the Compose orchestrator while reusing
managed PostgreSQL and Redis instances.

### Database Migrations

The project uses Alembic for migrations.

```bash
alembic upgrade head
```

To verify downgrade safety when targeting PostgreSQL run:

```bash
alembic downgrade base
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

### Anki CSV Import

To use your Anki cards as the main vocabulary source and preserve scheduling:

```bash
# Import a local Anki CSV for a specific user (by email)
python scripts/import_anki_csv.py \
  --user-email learner@example.com \
  --csv Anki_cards___2025-11-01T13-09-36.csv \
  --preserve-scheduling true

# Or select the user by UUID and override deck name
python scripts/import_anki_csv.py \
  --user-id 00000000-0000-0000-0000-000000000000 \
  --csv /absolute/path/to/export.csv \
  --deck-name "Französisch 5000"
```

Notes:

- The importer recognizes typical Anki columns like `question`, `answer`, `c_Deck`, `c_Due`, `c_LatestReview`,
  `c_Interval_in_Days`, `c_Ease`, `c_Reviews`, `c_Lapses`, and automatically pairs FR↔DE cards.
- Scheduling data (`due`/`interval`/`ease`/`reps`/`lapses`) is preserved when `--preserve-scheduling true` (default).
- After importing, the Progress page (web) pulls `/progress/anki` and `/progress/anki/summary` and the session
  suggestions use due cards from `/progress/queue`.

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

### Load Testing

Scenario scripts live in `tests/load/locustfile.py` and exercise the most common learner
flows (registration, session creation, conversational turns, and analytics reads).

```bash
locust -f tests/load/locustfile.py --host http://localhost:8000
```

Scale the number of simulated users to confirm the platform sustains 100 concurrent
learners with sub-500 ms p95 latency, as outlined in the roadmap.



## Background Tasks & Scheduled Jobs

The application uses Celery with Redis for background task processing and scheduled jobs.

### Running Celery Workers

**Development:**
```bash
# Start worker
celery -A app.celery_app worker --loglevel=info

# Start beat scheduler
celery -A app.celery_app beat --loglevel=info

# Start Flower monitoring UI
celery -A app.celery_app flower --port=5555
```

Access Flower dashboard at http://localhost:5555

**Production:**
```bash
docker compose -f docker/docker-compose.prod.yml up -d celery-worker celery-beat
```

### Scheduled Tasks

| Task | Schedule | Description |
|------|----------|-------------|
| `generate_daily_snapshots` | Daily at 2 AM UTC | Generate analytics snapshots for all active users |
| `cleanup_old_snapshots` | Weekly (Sunday 3 AM) | Remove snapshots older than 365 days |
| `send_streak_reminders` | Daily at 6 PM UTC | Send reminders to users with active streaks |

### Manual Task Execution

```bash
# Generate snapshots for all users
python scripts/trigger_analytics.py --date 2024-01-15

# Generate snapshot for specific user
python scripts/trigger_analytics.py --user-id <uuid>

# Queue task asynchronously
python scripts/trigger_analytics.py --async
```

## Achievement System

The platform includes a gamification layer that rewards learners for consistent practice and milestone achievements.

### Achievement Categories

- **Session**: Completing learning sessions
- **Streak**: Maintaining daily practice streaks (3, 7, 30 days)
- **Vocabulary**: Mastering vocabulary words (50, 200, 500 words)
- **XP**: Earning experience points (500, 2000, 5000 XP)
- **Accuracy**: High-accuracy performance (95%+ accuracy over 100 sessions)

### Seeding Achievements

```bash
python scripts/seed_achievements.py
```

### Achievement Endpoints

- `GET /api/v1/achievements` – List all available achievements
- `GET /api/v1/achievements/my` – Get current user's achievement progress
- `POST /api/v1/achievements/check` – Manually trigger achievement check

### Automatic Achievement Checking

Achievements are automatically checked and unlocked when:

- A learning session is completed
- The periodic Celery task runs (optional)

### Manual Achievement Check

```bash
# Trigger achievement check for specific user
python scripts/trigger_achievements.py --user-id <uuid>

# Queue task asynchronously
python scripts/trigger_achievements.py --user-id <uuid> --async
```



### Analytics & Cached Lookups

Learner dashboards are powered by the analytics endpoints exposed at `/api/v1/analytics`:

- `GET /analytics/summary` – headline XP, streak, mastery, and review workload metrics.
- `GET /analytics/statistics` – rolling time series for XP, accuracy, minutes practiced, and reviews.
- `GET /analytics/streak` – current/longest streak values plus a calendar heatmap window.
- `GET /analytics/vocabulary` – vocabulary mastery counts grouped by FSRS state.
- `GET /analytics/errors` – the most frequent learner mistakes captured during sessions.

These responses are cached for 15 minutes in Redis to minimise query load. Additional
caches back the vocabulary listing/detail endpoints (1 hour TTL), user profile reads
(5 minute TTL), and the due-review counters (60 second TTL). Cache invalidation is
triggered automatically whenever sessions complete, reviews are logged, or profiles are
updated to ensure dashboards stay fresh.

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

## Continuous Integration

Every push and pull request triggers the GitHub Actions workflow defined in
`.github/workflows/ci.yml`. The pipeline performs the following checks:

1. Installs dependencies (including spaCy) and runs Ruff linting.
2. Executes the pytest suite with coverage reporting.
3. Applies Alembic migrations against a PostgreSQL 15 service, downgrades back to base,
   and reapplies the head migration to guarantee reversibility.
4. Builds the production Docker image to catch packaging regressions.

CI logs are attached to pull requests so reviewers can confirm build health before
merging.

## Deployment Runbook

1. Build and push the container image: `docker build . -t ghcr.io/<org>/conversational-language-learning:TAG`.
2. Publish the image with `docker push` and update the staging Compose file if the tag changes.
3. Deploy to staging via `docker compose -f docker/docker-compose.staging.yml up -d` and run smoke tests (basic API calls plus a sample conversational session).
4. Promote to production by pulling the new tag and running `docker compose -f docker/docker-compose.prod.yml up -d`.
5. Monitor Redis/DB metrics and review the analytics endpoints for anomalies after rollout.

## Next Steps

- Implement the achievement service and learner badge endpoints.
- Integrate Prometheus exporters and Grafana dashboards for long-term observability.
- Build push-notification delivery (FCM/APNs) for streak reminders and session nudges.

Refer to the [project wiki](https://github.com/Pechst1/ConversationalLanguageLearning/wiki) for the comprehensive roadmap.
