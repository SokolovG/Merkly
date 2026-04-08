# TODOS

## T1: Consolidate BotStateStore

**What:** Move `_pending_sessions`, `_pending_writing`, and `_pending_listening` from
module-level globals into `BotStateStore`, then inject via Dishka.

**Why:** State is scattered across 3 modules with no single view of active sessions.
`BotStateStore` exists specifically for this purpose but is dead code. A single store
makes it trivial to add a TTL, debug active sessions, or migrate to Redis.

**Pros:** Single source of truth, enables TTL/cleanup, testable in isolation.

**Cons:** Touches all three handler files, requires adding a Dishka `Scope.APP` provider.

**Context:** The pattern was established in `commands.py` before `BotStateStore` was created.
The new `listening.py` handler correctly followed the existing (wrong) pattern.
`bot_state.py:1-17` defines the struct but nothing injects or uses it.
See: `src/infrastructure/telegram/bot_state.py`,
`src/infrastructure/telegram/handlers/commands.py:47-48`,
`src/infrastructure/telegram/handlers/listening.py:15`.

**Depends on:** None.

---

## T2: Add whisper healthcheck to docker-compose

**What:** Replace `condition: service_started` with a real healthcheck for the `whisper`
service in `docker-compose.yml`.

**Why:** The faster-whisper server loads the model (~500MB) on startup.
`service_started` fires the moment the container starts, not when the model is ready.
If the backend starts immediately and a user runs `/listen`, they get a
"connection refused" from whisper. The `db` service already has a correct healthcheck.

**Pros:** Eliminates cold-start failures after `docker compose up`.

**Cons:** Requires verifying the healthcheck endpoint for `fedirz/faster-whisper-server`
(likely `GET /health` or `GET /v1/models`).

**Context:** `docker-compose.yml:19-26`. The db service healthcheck pattern at
`docker-compose.yml:7-12` is the model to follow.

**Depends on:** None.
