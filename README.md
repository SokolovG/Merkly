# Language Tutor Bot

## What it does

A Telegram bot that runs structured daily language learning sessions. It fetches a news article in your target language, asks comprehension questions, reviews your answers like a teacher, and automatically creates Anki or Mochi flashcards for vocabulary gaps — without you touching your card app.

Supports any language your LLM knows. Article fetching uses multilingual RSS feeds + Wikipedia as a fallback, covering a wide range of languages out of the box.

<!-- TODO: add demo GIF -->

## Quickstart

**Requirements:** Docker, Docker Compose, a Telegram bot token, an LLM API key (OpenAI or compatible).

```bash
# 1. Clone the repo
git clone https://github.com/SokolovG/merkly.git
cd merkly

# 2. Configure environment
cp .env.example .env
# Edit .env — fill in TELEGRAM_TOKEN, LLM_API_KEY, and DB_PASSWORD at minimum

# 3. Start services
docker compose up --build -d

# 4. Run database migrations
make migrate

# 5. Open Telegram and send /start to your bot
```

The bot is now running. Send `/start` to begin onboarding.

## Configuration

Copy `.env.example` to `.env` and fill in the values below.

### Telegram

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `TELEGRAM_TOKEN` | Yes | — | Bot token from [@BotFather](https://t.me/BotFather) |

### LLM (any OpenAI-compatible endpoint)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `LLM_BASE_URL` | No | `https://api.openai.com/v1` | Base URL for your LLM provider |
| `LLM_API_KEY` | Yes | — | API key for your LLM provider |
| `LLM_MODEL` | No | `gpt-4o-mini` | Model name to use |

Compatible providers: OpenAI, Groq, Together, Mistral, Ollama (local).

### Card Backend

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `CARD_BACKEND` | No | `anki` | `"anki"` or `"mochi"` |
| `ANKI_CONNECT_URL` | No | `http://localhost:8765` | AnkiConnect endpoint |
| `ANKI_DECK` | No | `Language::Daily` | Default Anki deck name |
| `MOCHI_API_KEY` | If Mochi | — | API key from mochi.cards |
| `MOCHI_DECK_ID` | If Mochi | — | Target deck ID |
| `MOCHI_BASE_URL` | No | `https://app.mochi.cards/api` | Override for self-hosted Mochi |

### Database (Postgres)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DB_HOST` | No | `db` | Postgres host (`db` in Docker, `localhost` for local dev) |
| `DB_PORT` | No | `5432` | Postgres port |
| `DB_NAME` | No | `merkly` | Database name |
| `DB_USER` | No | `postgres` | Database user |
| `DB_PASSWORD` | Yes | — | Database password |

## Card Backends

### Anki

Requires the [AnkiConnect](https://ankiweb.net/shared/info/2055492159) plugin installed and Anki running on your machine.

> **Docker note:** If running the bot in Docker with `CARD_BACKEND=anki`, set:
> ```
> ANKI_CONNECT_URL=http://host.docker.internal:8765
> ```
> `localhost` inside a Docker container refers to the container itself, not your host machine.

### Mochi

Get an API key at [mochi.cards](https://mochi.cards) and find your deck ID in the Mochi web UI.

## Commands

| Command | Description |
|---------|-------------|
| `/start` | Start onboarding or resume if profile exists |
| `/session` | Start a daily reading lesson (article → questions → feedback) |
| `/vocab` | Generate vocabulary cards for a topic (`/vocab`, `/vocab 5`, `/vocab food`) |
| `/settings` | View and edit your profile, schedule, and learning strategy |
| `/newdeck <name>` | Create a new deck in your card backend |
| `/setdeck` | Switch your active deck |
| `/scheduler` | Toggle and configure the daily vocab scheduler |
| `+word` | Instantly create a flashcard for any word or phrase |

**`+word` examples:**
- `+Gemütlichkeit` — bot looks up meaning and creates a card
- `+oida/slang` — word + context hint for disambiguation
- `+Da warst du noch Quark im Schaufenster` — full phrase

## Makefile

| Command | Description |
|---------|-------------|
| `make migrate` | Apply all pending Alembic migrations |
| `make migration msg="..."` | Generate a new Alembic migration from model changes |

## Tech Stack

| Layer | Technology |
|-------|------------|
| Bot framework | aiogram 3 + aiogram-dialog |
| Dependency injection | dishka |
| Domain models | msgspec |
| LLM | Any OpenAI-compatible API (default: gpt-4o-mini) |
| Article source | Multilingual RSS feeds + Wikipedia fallback |
| Card backend | AnkiConnect or Mochi (switchable) |
| Scheduler | APScheduler |
| Database | Postgres (asyncpg + SQLAlchemy 2.0 async + Alembic) |
| Packaging | uv + hatchling (Python 3.12) |

## License

MIT — see [LICENSE](LICENSE) file.
