from backend.src.domain.exceptions import AppError


class InfrastructureError(AppError):
    """External service or I/O failure."""


class CardBackendError(InfrastructureError):
    """Anki or Mochi card operation failed."""


class FetcherError(InfrastructureError):
    """Article fetch failed (network, parse, no content)."""


class LLMError(InfrastructureError):
    """LLM call failed or returned unusable output."""
