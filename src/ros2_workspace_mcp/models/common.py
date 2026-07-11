"""Shared structured values returned by workspace tools."""

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Severity(str, Enum):
    """Stable severity values for scan issues."""

    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"


class ScanIssue(BaseModel):
    """A machine-readable, path-scoped scan problem."""

    model_config = ConfigDict(frozen=True)

    severity: Severity
    code: str
    message: str
    path: str
    package_name: str | None = None
    line: int | None = None
    column: int | None = None
    context: dict[str, Any] = Field(default_factory=dict)
