"""Application exception hierarchy.

Every exception raised within the system inherits from AppBaseError.
This enables catch-all handling at API layer without leaking raw library errors.

Import rule: any layer may import from here.
"""


class AppBaseError(Exception):
    """Base for all application exceptions. Carries structured detail."""

    def __init__(self, message: str, detail: dict | None = None) -> None:
        self.message = message
        self.detail = detail or {}
        super().__init__(message)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(message={self.message!r}, detail={self.detail})"


# ── Not Found ────────────────────────────────────────────────────────────────

class NotFoundError(AppBaseError):
    """Requested resource does not exist."""


class JobNotFoundError(NotFoundError):
    """Job requirement not found."""


class CandidateNotFoundError(NotFoundError):
    """Candidate record not found."""


class BatchNotFoundError(NotFoundError):
    """Batch record not found."""


# ── Duplicate ────────────────────────────────────────────────────────────────

class DuplicateError(AppBaseError):
    """Resource already exists."""


class DuplicateCVError(DuplicateError):
    """CV with identical content already submitted for this job."""


# ── Validation ───────────────────────────────────────────────────────────────

class ValidationError(AppBaseError):
    """Input validation failure."""


class FileValidationError(ValidationError):
    """Uploaded file is invalid (bad type, corrupt, empty)."""


class FileTooLargeError(ValidationError):
    """Uploaded file exceeds MAX_FILE_SIZE_MB limit."""


class InvalidStatusTransitionError(ValidationError):
    """Requested status transition is not permitted."""


# ── Persistence ───────────────────────────────────────────────────────────────

class PersistenceError(AppBaseError):
    """Database read/write failure."""


# ── Storage ───────────────────────────────────────────────────────────────────

class StorageError(AppBaseError):
    """File storage operation failure (local or S3)."""


# ── Cache ─────────────────────────────────────────────────────────────────────

class CacheError(AppBaseError):
    """Redis cache operation failure. Non-critical — system continues without cache."""


# ── Document Extraction ───────────────────────────────────────────────────────

class DocumentExtractionError(AppBaseError):
    """Docling failed to extract text from document."""


# ── Crew / AI ────────────────────────────────────────────────────────────────

class CrewExecutionError(AppBaseError):
    """CrewAI pipeline failure. Base for all crew-related errors."""


class AgentExecutionError(CrewExecutionError):
    """Specific agent within the crew failed."""

    def __init__(self, message: str, agent_name: str, detail: dict | None = None) -> None:
        super().__init__(message, detail)
        self.agent_name = agent_name


class TokenBudgetExceededError(CrewExecutionError):
    """Token usage exceeded configured budget. May carry partial result."""

    def __init__(
        self,
        message: str,
        used: int,
        budget: int,
        detail: dict | None = None,
    ) -> None:
        super().__init__(message, detail)
        self.used = used
        self.budget = budget


class CrewTimeoutError(CrewExecutionError):
    """Crew execution exceeded CREW_EXECUTION_TIMEOUT."""


# ── Tracing ───────────────────────────────────────────────────────────────────

class TracingError(AppBaseError):
    """Langfuse tracing failure. Non-critical — system continues without tracing."""
