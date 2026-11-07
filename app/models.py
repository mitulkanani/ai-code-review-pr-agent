from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Severity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class ReviewCategory(StrEnum):
    SECURITY = "security"
    BUG = "bug"
    RELIABILITY = "reliability"
    PERFORMANCE = "performance"
    MAINTAINABILITY = "maintainability"
    TESTING = "testing"


class ChangedFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str = Field(min_length=1, max_length=500)
    status: str = "modified"
    patch: str | None = Field(default=None, max_length=120_000)

    @field_validator("path")
    @classmethod
    def path_must_be_relative(cls, value: str) -> str:
        normalized = value.replace("\\", "/")
        if normalized.startswith("/") or ".." in normalized.split("/"):
            raise ValueError("File path must be repository-relative.")
        return normalized


class ReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    repository: str = Field(min_length=3, max_length=200, pattern=r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
    pull_request: int = Field(ge=1)
    title: str = Field(default="", max_length=500)
    body: str = Field(default="", max_length=10_000)
    head_sha: str = Field(default="", max_length=100)
    files: list[ChangedFile] = Field(min_length=1, max_length=100)


class Finding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rule_id: str
    category: ReviewCategory
    severity: Severity
    title: str = Field(min_length=4, max_length=160)
    description: str = Field(min_length=8, max_length=2000)
    recommendation: str = Field(default="", max_length=1200)
    path: str
    line: int = Field(ge=1)
    confidence: float = Field(ge=0, le=1)
    source: str = "static"


class FileSummary(BaseModel):
    path: str
    status: str
    additions: int = 0
    deletions: int = 0
    analyzed_added_lines: int = 0


class ReviewSummary(BaseModel):
    total_findings: int
    critical: int
    high: int
    medium: int
    low: int
    info: int
    changed_files: int
    analyzed_added_lines: int


class ReviewResult(BaseModel):
    review_id: UUID = Field(default_factory=uuid4)
    repository: str
    pull_request: int
    head_sha: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    provider: str
    summary: ReviewSummary
    findings: list[Finding]
    files: list[FileSummary]
    notes: list[str] = Field(default_factory=list)


class ApiReviewResponse(BaseModel):
    review_id: UUID
    status: str
    result: ReviewResult


class HealthResponse(BaseModel):
    status: str
    version: str


class LLMFinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: ReviewCategory
    severity: Severity
    title: str
    description: str
    recommendation: str
    path: str
    line: int
    confidence: float

    @field_validator("line")
    @classmethod
    def line_must_be_positive(cls, value: int) -> int:
        if value < 1:
            raise ValueError("Line must be a positive integer.")
        return value

    @field_validator("confidence")
    @classmethod
    def confidence_must_be_between_zero_and_one(cls, value: float) -> float:
        if not 0 <= value <= 1:
            raise ValueError("Confidence must be between 0 and 1.")
        return value


class LLMReviewPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    findings: list[LLMFinding]


class StoredReview(BaseModel):
    id: UUID
    repository: str
    pull_request: int
    result: dict[str, Any]
