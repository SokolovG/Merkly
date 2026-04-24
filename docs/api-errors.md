# API Error Reference

All error responses share the same envelope:

```json
{
  "success": false,
  "error_code": "NOT_FOUND",
  "message": "Identity not found with id: telegram:321504227",
  "details": { "resource": "Identity", "resource_id": "telegram:321504227" }
}
```

`details` is omitted when empty.

---

## Error codes by status

### 400 Bad Request

| `error_code` | When | `details` |
|---|---|---|
| `API_ERROR` | Generic client error (base class fallback) | — |
| `VALIDATION_ERROR` | Request body fails schema validation (msgspec decode) | — |

### 401 Unauthorized

| `error_code` | When | `details` |
|---|---|---|
| `AUTH_ERROR` | Missing or invalid `Authorization: Bearer <key>` header | — |

Litestar also emits this as `HTTP_401` (see below) for guard failures.

### 403 Forbidden

| `error_code` | When | `details` |
|---|---|---|
| `FORBIDDEN` | Authenticated but not allowed to perform this action | — |

### 404 Not Found

| `error_code` | When | `details` |
|---|---|---|
| `NOT_FOUND` | Resource does not exist | `resource`, `resource_id` |

Common `resource` values: `"Identity"`, `"Profile"`, `"Session"`.

Example:
```json
{
  "success": false,
  "error_code": "NOT_FOUND",
  "message": "Identity not found with id: telegram:321504227",
  "details": { "resource": "Identity", "resource_id": "telegram:321504227" }
}
```

### 409 Conflict

| `error_code` | When | `details` |
|---|---|---|
| `CONFLICT` | Resource state conflict (e.g. duplicate, wrong state) | — |

Example: submitting `/answer` when session is already in `"writing"` state.

### 500 Internal Server Error

| `error_code` | When | `details` |
|---|---|---|
| `INTERNAL_ERROR` | Unhandled exception — database failure, LLM timeout, etc. | — |

500s are logged at `ERROR` level with full traceback. `details` is intentionally empty to avoid leaking internals.

---

## HTTP passthrough codes

Litestar framework errors (route not found, method not allowed, etc.) are caught by
`ErrorHandlerMiddleware` and wrapped with a generic `HTTP_<code>` error code:

| `error_code` | HTTP status | When |
|---|---|---|
| `HTTP_401` | 401 | Guard rejects the API key |
| `HTTP_404` | 404 | Route not found |
| `HTTP_405` | 405 | Method not allowed |
| `HTTP_422` | 422 | Path/query parameter validation failed |

---

## `already_exists` field — vocab capture

`POST /api/vocab/word` always returns **200**. Duplicate detection is signalled
via a field in the response body, not via 4xx:

```json
{
  "success": true,
  "data": {
    "already_exists": true,
    "card": { "word": "Brot", "translation": "", "example_sentence": "", "word_type": "noun" },
    "pool_card_id": ""
  },
  "message": "Word already in history"
}
```

When `already_exists: true`, `card` and `pool_card_id` are placeholder values and
should be ignored. Callers must check this field before rendering a card.

---

## Raising errors in use cases

Use the typed subclasses from `backend.src.infrastructure.exceptions`:

```python
from backend.src.infrastructure.exceptions import (
    NotFoundError,
    ConflictError,
    ValidationError,
    InternalServerError,
)

# 404
raise NotFoundError("Session", session_id)

# 409
raise ConflictError("Session is not in answering state")

# Wrap unexpected I/O errors so details stay internal
try:
    result = await self._repo.get(...)
except NotFoundError:
    raise  # let it bubble as-is
except Exception as exc:
    raise InternalServerError(
        message="Failed to fetch session",
        details={"session_id": session_id},
    ) from exc
```
