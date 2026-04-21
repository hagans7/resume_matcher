"""ExtractedDocument entity.

Output of DoclingExtractorClient.extract().
Represents structured text content extracted from a PDF or DOCX file.
Passed from PrepareCVTextService to the CrewAI matcher as cleaned text.
"""

from dataclasses import dataclass, field

MIN_CONTENT_LENGTH = 50     # below this, extraction is considered failed


@dataclass
class Section:
    """A document section identified by Docling: heading + body text."""
    heading: str
    content: str


@dataclass
class ExtractedDocument:
    raw_text: str               # full document text, concatenated
    sections: list[Section]     # structured sections (heading + content)
    page_count: int
    has_tables: bool

    def has_content(self) -> bool:
        """Check if extraction produced usable text (not empty or near-empty)."""
        return len(self.raw_text.strip()) >= MIN_CONTENT_LENGTH

    def text_length(self) -> int:
        """Return character count of raw_text."""
        return len(self.raw_text)
