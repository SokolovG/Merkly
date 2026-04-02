class AppError(Exception):
    """Base for all application errors."""


class DomainError(AppError):
    """Business rule violations."""


class WordCaptureError(DomainError):
    """Failed to capture or generate a vocabulary card."""


class LessonError(DomainError):
    """Failed to prepare or review a lesson."""


class ProfileError(DomainError):
    """User profile missing or invalid."""
