"""Pydantic models for mtui Gmail TUI."""

from pydantic import BaseModel, Field
from typing import Optional


class Attachment(BaseModel):
    """Email attachment metadata."""

    message_id: str = ""
    part_id: int = 0
    filename: str = ""
    content_type: str = "application/octet-stream"
    size_bytes: int = 0

    @property
    def size_display(self) -> str:
        if self.size_bytes < 1024:
            return f"{self.size_bytes}B"
        elif self.size_bytes < 1048576:
            return f"{self.size_bytes // 1024}KB"
        return f"{self.size_bytes // 1048576}MB"


class EmailHeaders(BaseModel):
    """Email headers."""

    subject: Optional[str] = "(no subject)"
    from_: Optional[str] = Field(default="Unknown", alias="from")
    to: Optional[str] = "Unknown"
    date: Optional[str] = "Unknown"
    cc: Optional[str] = None
    reply_to: Optional[str] = None

    class Config:
        populate_by_name = True


class EmailMessage(BaseModel):
    """Full email message content."""

    message_id: str = ""
    headers: EmailHeaders = Field(default_factory=EmailHeaders)
    body_plain: str = ""
    body_html: str = ""
    body_markdown: str = ""
    attachments: list[Attachment] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)

    @property
    def display_body(self) -> str:
        """Return best available body content."""
        return self.body_markdown or self.body_plain or "(no content)"

    @property
    def has_attachments(self) -> bool:
        return len(self.attachments) > 0


class EmailThread(BaseModel):
    """Email thread summary from search results."""

    thread_id: str
    timestamp: int = 0
    date_relative: str = ""
    authors: str = ""
    subject: str = ""
    tags: list[str] = Field(default_factory=list)
    total_messages: int = 1
    matched_messages: int = 0
    has_attachments: bool = False

    @property
    def is_unread(self) -> bool:
        return "unread" in self.tags

    @property
    def is_flagged(self) -> bool:
        return "flagged" in self.tags

    @property
    def flags_display(self) -> str:
        """Return flag indicators for display."""
        flags = ""
        if self.is_flagged:
            flags += "★"
        if self.has_attachments:
            flags += "📎"
        if self.is_unread:
            flags += "●"
        return flags


class SearchResult(BaseModel):
    """Search result containing list of threads."""

    threads: list[EmailThread] = Field(default_factory=list)
    total_count: int = 0
    query: str = ""


class AttachmentList(BaseModel):
    """List of attachments from mget."""

    attachments: list[Attachment] = Field(default_factory=list)
