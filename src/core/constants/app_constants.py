"""Application-wide constants. No logic — values only.

Import rule: any layer may import from here.
All string constants use module-level variables (not Enum) for simplicity
and direct compatibility with DB string columns.
"""

# ── Candidate Status ──────────────────────────────────────────────────────────
# Lifecycle: new → processing → evaluated → reviewed | rejected | hired
CANDIDATE_STATUS_NEW = "new"
CANDIDATE_STATUS_PROCESSING = "processing"
CANDIDATE_STATUS_EVALUATED = "evaluated"
CANDIDATE_STATUS_REVIEWED = "reviewed"
CANDIDATE_STATUS_REJECTED = "rejected"
CANDIDATE_STATUS_HIRED = "hired"
CANDIDATE_STATUS_FAILED = "failed"

# Valid HR-driven status transitions after evaluation.
# Key = current status, Value = set of allowed next statuses.
# Used by ReviewCandidateService for O(1) transition validation.
VALID_STATUS_TRANSITIONS: dict[str, set[str]] = {
    CANDIDATE_STATUS_EVALUATED: {
        CANDIDATE_STATUS_REVIEWED,
        CANDIDATE_STATUS_REJECTED,
    },
    CANDIDATE_STATUS_REVIEWED: {
        CANDIDATE_STATUS_HIRED,
        CANDIDATE_STATUS_REJECTED,
    },
}

# ── Batch Status ──────────────────────────────────────────────────────────────
BATCH_STATUS_QUEUED = "queued"
BATCH_STATUS_PROCESSING = "processing"
BATCH_STATUS_COMPLETED = "completed"
BATCH_STATUS_PARTIAL_FAILURE = "partial_failure"
BATCH_STATUS_CANCELLED = "cancelled"

# ── Job Status ────────────────────────────────────────────────────────────────
JOB_STATUS_ACTIVE = "active"
JOB_STATUS_ARCHIVED = "archived"

# ── Evaluation Verdict ────────────────────────────────────────────────────────
VERDICT_SHORTLIST = "shortlist"
VERDICT_REVIEW = "review"
VERDICT_REJECT = "reject"

# ── Evaluation (Crew) Profile ─────────────────────────────────────────────────
EVALUATION_MODE_QUICK = "quick"
EVALUATION_MODE_STANDARD = "standard"
EVALUATION_MODE_FULL = "full"

VALID_EVALUATION_MODES = {
    EVALUATION_MODE_QUICK,
    EVALUATION_MODE_STANDARD,
    EVALUATION_MODE_FULL,
}

# ── File Handling ─────────────────────────────────────────────────────────────
ALLOWED_FILE_EXTENSIONS = {".pdf", ".docx"}
HASH_ALGORITHM = "sha256"

# ── Celery ────────────────────────────────────────────────────────────────────
MAX_RETRY_COUNT = 3
RETRY_DELAY_SECONDS = 30

# ── Cache ─────────────────────────────────────────────────────────────────────
JD_CACHE_TTL_SECONDS = 86_400   # 24 hours — JD benchmark rarely changes within a day

# ── Scoring ───────────────────────────────────────────────────────────────────
# Verdict thresholds applied by Score Aggregator agent.
# Stored here as reference — agent prompt also contains these values.
SCORE_SHORTLIST_MIN = 75
SCORE_REVIEW_MIN = 50
# Below SCORE_REVIEW_MIN → VERDICT_REJECT

# ── Profile Detection Keywords ────────────────────────────────────────────────
# Used by _determine_profile() in EvaluateResumeService.
# Simple keyword matching in Python — runs before CrewAI to select crew profile.
PROJECT_SECTION_KEYWORDS = {
    "project", "projects", "portfolio", "case study", "case studies",
    "work sample", "open source", "github",
}
SOFT_SKILL_JD_KEYWORDS = {
    "team player", "teamwork", "leadership", "communication", "interpersonal",
    "collaboration", "problem solving", "adaptable", "proactive", "initiative",
    "culture fit", "emotional intelligence", "mentoring",
}
