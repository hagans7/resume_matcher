"""MaskPIIService — strips personally identifiable information from CV text.

Runs BEFORE crew execution. Ensures LLM never receives raw PII.
Regex-based: O(k*n) where k = number of patterns (~6), n = text length.
Acceptable for documents up to ~50KB.

Masked fields:
  - Email addresses       → [EMAIL]
  - Phone numbers         → [PHONE]
  - Indonesian NIK (16-digit) → [NIK]
  - URLs / LinkedIn       → [URL]
  - Physical addresses (partial) → not masked (location context needed for JD matching)

Note: Name masking is intentionally NOT done here.
Candidate name is stored separately in original_filename and candidate record.
The CV text passed to LLM is used for skill/experience analysis only.
"""


import re

from src.core.logging.logger import get_logger

logger = get_logger(__name__)

# Compiled regex patterns — compiled once at module load.
# ORDER MATTERS: more specific patterns must run before more general ones.
# NIK (16-digit) must run before phone — phone regex would otherwise consume
# a substring of the NIK (e.g. "01234567890001" inside "3201234567890001").
_PATTERNS: list[tuple[re.Pattern, str]] = [
    # Email — run first, unambiguous
    (
        re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", re.IGNORECASE),
        "[EMAIL]",
    ),
    # Indonesian NIK — exactly 16 digits, whole word boundary.
    # Must run BEFORE phone pattern to prevent phone regex consuming NIK substrings.
    (
        re.compile(r"\b\d{16}\b"),
        "[NIK]",
    ),
    # Phone — covers Indonesian formats: +62, 08xx, (021), etc.
    # Negative lookbehind (?<!\d) prevents matching digits already part of a longer number.
    (
        re.compile(
            r"(?<!\d)(\+62|0)[0-9\-\s\(\)]{8,14}(?!\d)",
            re.IGNORECASE,
        ),
        "[PHONE]",
    ),
    # URLs (http/https/www)
    (
        re.compile(
            r"https?://[^\s<>\"]+|www\.[^\s<>\"]+",
            re.IGNORECASE,
        ),
        "[URL]",
    ),
    # LinkedIn profile (fallback if URL pattern misses plain linkedin.com/in/...)
    (
        re.compile(r"linkedin\.com/in/[^\s,<>\"]+", re.IGNORECASE),
        "[URL]",
    ),
    # GitHub profile
    (
        re.compile(r"github\.com/[^\s,<>\"]+", re.IGNORECASE),
        "[URL]",
    ),
]


class MaskPIIService:
    """Stateless PII masking service. No external dependencies."""

    def execute(self, text: str) -> str:
        """Apply all PII patterns to text. Returns masked copy. Never mutates input."""
        masked = text
        replacements = 0

        for pattern, replacement in _PATTERNS:
            new_text, count = pattern.subn(replacement, masked)
            replacements += count
            masked = new_text

        if replacements > 0:
            logger.debug("pii_masked", replacement_count=replacements)

        return masked