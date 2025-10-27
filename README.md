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

### Running with Docker

Container orchestration is provided via Compose files in the `docker/` directory.

**Local development with hot reload**

```bash
cp .env.example .env
docker compose -f docker/docker-compose.dev.yml up --build
```

The API is exposed at http://localhost:8000 and automatically reloads when you edit
source files. PostgreSQL and Redis data are stored in local Docker volumes.

**Staging environment preview**

```bash
cp .env.example .env.staging  # populate with staging secrets
docker compose -f docker/docker-compose.staging.yml up --detach
```

The staging compose file assumes you have already published a container image to the
GitHub Container Registry (`ghcr.io/pechst1/conversational-language-learning:latest`).

## Mobile Client (Expo)

The `mobile/` directory hosts an Expo-managed React Native client that targets iOS for
TestFlight distribution.

### Prerequisites

- Node.js 18+
- `npm` 9+ or `yarn` 1.22+
- Expo CLI (`npm install -g expo-cli`) and EAS CLI (`npm install -g eas-cli`)

### Local development

```bash
cd mobile
cp .env.example .env
npm install
npm run start
```

Expo will display a QR code to launch the iOS simulator or a physical device via the Expo
Go app. Update `.env` whenever API endpoints or feature toggles change.

### Environment variables

The mobile client reads configuration from build-time environment variables prefixed with
`EXPO_PUBLIC_`. Copy `mobile/.env.example` and update the values for your deployment:

| Variable | Description |
| --- | --- |
| `EXPO_PUBLIC_API_BASE_URL` | Required. Points to the production Conversational Language Learning API. |
| `EXPO_PUBLIC_API_BASE_URL_STAGING` | Optional. Overrides the API host for preview and staging builds. |
| `EXPO_PUBLIC_FEATURE_FLAG_SPEECH_TRAINER` | Enables or disables the speech pronunciation trainer modules. |
| `EXPO_PUBLIC_FEATURE_FLAG_GRAMMAR_HINTS` | Toggles inline grammar hints for lessons. |

Set these variables in `.env` for local runs and in your CI/CD secrets when creating EAS
builds.

### TestFlight builds

EAS CI is configured via `mobile/eas.json`. To produce a TestFlight artifact from CI or a
developer workstation run:

```bash
cd mobile
eas build --platform ios --profile production
eas submit --platform ios --profile production
```

The `production` profile uses the managed workflow, increments the build number
automatically, and targets the App Store Connect project defined in the submit section.

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

- Add Celery beat scheduling to generate nightly analytics snapshots automatically.
- Integrate Prometheus exporters and Grafana dashboards for long-term observability.
- Experiment with adaptive conversation personas powered by live evaluation metrics.

Refer to the [project wiki](https://github.com/Pechst1/ConversationalLanguageLearning/wiki) for the comprehensive roadmap.
