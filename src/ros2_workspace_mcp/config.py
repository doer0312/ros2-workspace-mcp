"""Validated, immutable server configuration."""

from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator
from pydantic_core import PydanticCustomError

from ros2_workspace_mcp import __version__
from ros2_workspace_mcp.security.paths import (
    InvalidWorkspacePathError,
    normalize_workspace_root,
)


class ServerSettings(BaseModel):
    """Runtime settings for one workspace-bound server instance."""

    model_config = ConfigDict(frozen=True)

    root_path: Path
    server_name: str = "ros2-workspace-inspector"
    server_version: str = __version__

    @field_validator("root_path", mode="before")
    @classmethod
    def validate_root_path(cls, value: Any) -> Path:
        """Resolve and validate the configured workspace root."""
        try:
            return normalize_workspace_root(value)
        except InvalidWorkspacePathError as exc:
            raise PydanticCustomError("workspace_path", str(exc)) from exc
