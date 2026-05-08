"""Central configuration for the CAD AI evaluation pipeline."""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _project_root() -> Path:
    override = os.getenv("CAD_EVAL_PROJECT_ROOT", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_project_root() / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # API
    gemini_api_key: str = Field(default="", description="Google Gemini API key")
    gemini_model: str = Field(default="gemini-3.1-pro-preview", description="Gemini model name (production-tested)")

    # Google Sheets
    google_sheets_credentials: Path = Field(
        default_factory=lambda: _project_root() / "credentials" / "service_account.json",
        description="Path to Google service account JSON key",
    )
    google_sheet_id: str = Field(default="", description="Target Google Sheet ID")
    google_sheet_tab: str = Field(default="Evaluation Results", description="Worksheet tab name")
    google_drive_folder_id: str = Field(
        default="",
        description="Optional Google Drive folder ID to store/report input image thumbnails",
    )

    # Retry
    max_retries: int = Field(default=3, ge=1, le=10)
    retry_delay: float = Field(default=2.0, ge=0.5)
    max_quota_backoff_seconds: int = Field(default=90, ge=5, le=600)

    # Generation runtime controls
    request_timeout_ms: int = Field(default=60000, ge=5000, le=300000)
    inter_request_delay: float = Field(default=1.0, ge=0.0, le=30.0)

    # Paths
    project_root: Path = Field(default_factory=_project_root)
    data_dir: Path = Field(default_factory=lambda: _project_root() / "data")
    output_dir: Path = Field(default_factory=lambda: _project_root() / "output")

    # Evaluation
    dxf_tolerance: float = Field(default=0.5, description="Coordinate matching tolerance")

    # Image conversion
    image_dpi: int = Field(default=300, ge=72, le=600)
    image_format: str = Field(default="png")

    # Logging
    log_level: str = Field(default="INFO")

    @property
    def dxf_dir(self) -> Path:
        return self.data_dir / "dxf"

    @property
    def images_dir(self) -> Path:
        return self.data_dir / "images"

    @property
    def generated_dir(self) -> Path:
        return self.data_dir / "generated"

    @property
    def reports_dir(self) -> Path:
        return self.output_dir / "reports"

    @property
    def comparisons_dir(self) -> Path:
        return self.output_dir / "comparisons"

    def ensure_dirs(self) -> None:
        for d in [
            self.dxf_dir / "manufacturing",
            self.dxf_dir / "construction",
            self.images_dir / "manufacturing",
            self.images_dir / "construction",
            self.generated_dir,
            self.reports_dir,
            self.comparisons_dir,
        ]:
            d.mkdir(parents=True, exist_ok=True)


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
