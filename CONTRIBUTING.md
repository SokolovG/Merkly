# Contributing

Technical guide for contributors. Covers architecture, the DI pattern, and how to extend the bot.

## Architecture Overview

The codebase uses a strict 4-layer architecture:

```
src/
├── domain/          # Pure domain — no I/O, no frameworks
│   ├── entities.py  # Data models (msgspec.Struct)
│   ├── enums.py     # Domain enums (StrEnum)
│   ├── constants.py # Language flags, names, and other data constants
│   └── ports/       # Abstract interfaces (ABC) for all I/O boundaries
│       ├── card_gateway.py
│       ├── profile_repo.py
│       ├── session_repo.py
│       └── article_fetcher.py
│
├── application/     # Agent loop — depends only on domain
│   └── agent/
│       ├── core.py   # LessonAgent — orchestrates tools
│       ├── prompts.py
│       └── tools.py
│
├── infrastructure/  # Implementations of domain ports + Telegram handlers
│   ├── card_backends/   # AnkiClient, MochiClient
│   ├── database/        # SQLAlchemy models + Postgres repositories
│   ├── fetchers/        # Article fetchers (RSS feeds, Wikipedia)
│   ├── llm/             # LLM client wrapper
│   ├── scheduler/       # APScheduler jobs
│   └── telegram/        # aiogram handlers, dialogs, messages
│
├── config.py        # pydantic-settings — all env vars
└── dependencies.py  # dishka DI container (AppProvider)
```

**Rule:** domain never imports from infrastructure. Infrastructure imports from domain.

## Dependency Injection (dishka)

All dependencies are wired in `src/dependencies.py` via `AppProvider`.

**In aiogram handlers** — use `FromDishka[T]` in the function signature:

```python
from dishka.integrations.aiogram import FromDishka

@router.message(Command("session"))
async def cmd_session(
    message: Message,
    profile_repo: FromDishka[ProfileRepository],
    agent: FromDishka[LessonAgent],
) -> None:
    ...
```

**In aiogram-dialog callbacks** — `on_click` has a fixed 3-arg signature so `FromDishka` is not available. Access the container via middleware data:

```python
async def on_confirm(callback, widget, manager: DialogManager):
    container = manager.middleware_data["dishka_container"]
    profile_repo = await container.get(ProfileRepository)
    ...
```

**Scopes:**

| Scope | Lifetime | Use for |
|-------|----------|---------|
| `Scope.APP` | Singleton for app lifetime | LLM client, card gateway, scheduler |
| `Scope.REQUEST` | Per Telegram update | DB session, repositories |

## How to Add a Card Backend

1. **Create the implementation:**

   ```
   src/infrastructure/card_backends/your_backend.py
   ```

2. **Inherit from `ICardGateway`** (`src/domain/ports/card_gateway.py`):

   ```python
   from src.domain.ports.card_gateway import ICardGateway

   class YourBackendClient(ICardGateway):
       async def create_card(self, card: VocabCard, deck_id: str | None = None) -> str | None: ...
       async def delete_card(self, card_id: str) -> bool: ...
       async def is_available(self) -> bool: ...
       async def create_deck(self, name: str) -> str: ...
       async def list_decks(self) -> list[tuple[str, str]]: ...
   ```

   Python will raise `TypeError` at import time if any abstract method is missing.

3. **Add config fields** to `src/config.py`:

   ```python
   YOUR_BACKEND_API_KEY: SecretStr = SecretStr("")
   YOUR_BACKEND_DECK_ID: str = ""
   ```

4. **Wire in** `src/dependencies.py` — add a case to the `card_gateway()` match:

   ```python
   case CardBackend.YOUR_BACKEND:
       return YourBackendClient(
           api_key=settings.YOUR_BACKEND_API_KEY.get_secret_value(),
           deck_id=settings.YOUR_BACKEND_DECK_ID,
       )
   ```

5. **Add the backend name** to the `CARD_BACKEND` Literal in `config.py`:

   ```python
   CARD_BACKEND: Literal["anki", "mochi", "your_backend"] = "anki"
   ```

## How to Add a Language Fetcher

1. **Create the implementation:**

   ```
   src/infrastructure/fetchers/{language}/your_source.py
   ```

2. **Inherit from `IArticleFetcher`** (`src/domain/ports/article_fetcher.py`):

   ```python
   from src.domain.ports.article_fetcher import IArticleFetcher, Article

   class YourFetcher(IArticleFetcher):
       async def fetch(self, level: str, language: str, source_url: str | None = None) -> Article:
           ...
   ```

3. **Wire in** `src/dependencies.py` — update `article_fetcher()` to return your fetcher or add language-routing logic.

## Code Style

- Python 3.12, strict typing throughout
- `StrEnum` for all domain enums — values serialize as plain strings (msgspec transparent)
- All bot reply strings go in `src/infrastructure/telegram/messages.py` — handlers import from there, no hardcoded strings in handler files
- Language data (flags, names) lives in `src/domain/constants.py`

Before committing:

```bash
uv run ruff check src/
uv run ruff format src/
```

## Running Locally (without Docker)

```bash
# Install dependencies
uv sync

# Start Postgres (e.g. via Docker on a different port)
docker run -d -p 5433:5432 -e POSTGRES_PASSWORD=postgres postgres:16

# Run migrations
DB_HOST=localhost DB_PORT=5433 DB_NAME=merkly DB_USER=postgres DB_PASSWORD=postgres \
  uv run alembic upgrade head

# Start the bot
uv run python -m src.main
```

Make sure `.env` is present with at least `TELEGRAM_TOKEN`, `LLM_API_KEY`, and `DB_*` fields set.
