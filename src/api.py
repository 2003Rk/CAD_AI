"""FastAPI REST backend for the CAD Eval pipeline.

Start with:
    uvicorn src.api:app --host 0.0.0.0 --port 8000

Or via the CLI:
    cad-eval api --host 0.0.0.0 --port 8000

Environment variables:
    CORS_ORIGINS   Comma-separated list of allowed frontend origins.
                   Defaults to "*" (all). Set a specific origin in production,
                   e.g. CORS_ORIGINS=https://your-frontend.com
"""

from __future__ import annotations

import os
import re
import threading
import traceback
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from src.config import get_settings
from src.pipeline import run_full_pipeline

# Strip ANSI control codes (Rich colours, cursor ops, OSC hyperlinks)
_ANSI_CSI_RE = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")
_ANSI_OSC_RE = re.compile(r"\x1B\][^\x07\x1B]*(?:\x07|\x1B\\)")


# ---------------------------------------------------------------------------
# Shared pipeline state (single-process, thread-safe)
# ---------------------------------------------------------------------------

class _LogCollector:
    """File-like writer that feeds lines into _RunState."""

    def __init__(self, state: _RunState) -> None:
        self._state = state

    def write(self, text: str) -> int:
        if text:
            self._state.append_log(text)
        return len(text)

    def flush(self) -> None:
        return None


@dataclass
class _RunState:
    status: str = "idle"
    logs: list[str] = field(default_factory=list)
    progress: dict[str, Any] = field(
        default_factory=lambda: {
            "stage": "idle",
            "detail": "Not started",
            "completed": 0,
            "total": 1,
            "current": 0,
            "count_total": 0,
            "percent": 0.0,
        }
    )
    lock: threading.Lock = field(default_factory=threading.Lock)

    def append_log(self, text: str) -> None:
        with self.lock:
            clean = _ANSI_OSC_RE.sub("", text)
            clean = _ANSI_CSI_RE.sub("", clean)
            for part in clean.replace("\r", "").split("\n"):
                if part.strip():
                    self.logs.append(part)
            if len(self.logs) > 2000:
                self.logs = self.logs[-2000:]

    def set_status(self, value: str) -> None:
        with self.lock:
            self.status = value

    def set_progress(self, value: dict[str, Any]) -> None:
        with self.lock:
            self.progress = dict(value)

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            return {
                "status": self.status,
                "logs": list(self.logs),
                "progress": dict(self.progress),
            }


_STATE = _RunState()


# ---------------------------------------------------------------------------
# Pipeline helpers
# ---------------------------------------------------------------------------

def _has_runtime_files(root: Path, pattern: str) -> bool:
    return any(root.rglob(pattern))


def _resolve_pipeline_reuse_flags() -> tuple[bool, bool]:
    settings = get_settings()
    has_dxf = _has_runtime_files(settings.dxf_dir, "*.dxf")
    has_images = _has_runtime_files(settings.images_dir, f"*.{settings.image_format}")
    return has_dxf, (has_dxf and has_images)


def _run_pipeline_worker(pattern: str, skip_dataset: bool, skip_convert: bool) -> None:
    _STATE.set_status("running")
    with _STATE.lock:
        _STATE.logs = []
    _STATE.set_progress(
        {
            "stage": "starting",
            "detail": "Initializing",
            "completed": 0,
            "total": 1,
            "current": 0,
            "count_total": 0,
            "percent": 0.0,
        }
    )
    collector = _LogCollector(_STATE)
    try:
        pattern_ids = None if pattern == "all" else [int(pattern)]

        def _progress_cb(event: dict[str, Any]) -> None:
            _STATE.set_progress(event)

        with redirect_stdout(collector), redirect_stderr(collector):
            run_full_pipeline(
                pattern_ids=pattern_ids,
                skip_dataset=skip_dataset,
                skip_convert=skip_convert,
                progress_callback=_progress_cb,
            )
        _STATE.set_status("success")
    except Exception:
        _STATE.append_log(traceback.format_exc())
        _STATE.set_status("error")


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------

app = FastAPI(
    title="CAD Eval API",
    version="1.0.0",
    description="REST backend for the CAD AI evaluation pipeline.",
)

# CORS — set CORS_ORIGINS env var in production, e.g. https://your-frontend.com
_cors_origins = [o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class StartRequest(BaseModel):
    pattern: str = "all"


# ---------------------------------------------------------------------------
# API endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
def health() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok"}


@app.get("/api/status")
def api_status() -> dict[str, Any]:
    """Return current pipeline status, progress, and recent log lines."""
    return _STATE.snapshot()


@app.post("/api/start", status_code=202)
def api_start(body: StartRequest) -> dict[str, Any]:
    """Start the evaluation pipeline.

    Returns 202 Accepted immediately; poll /api/status for progress.
    Returns 409 if a run is already in progress.
    """
    if body.pattern not in {"all", "1", "2", "3"}:
        raise HTTPException(
            status_code=400,
            detail="pattern must be one of: all, 1, 2, 3",
        )

    if _STATE.snapshot()["status"] == "running":
        raise HTTPException(status_code=409, detail="Pipeline is already running")

    skip_dataset, skip_convert = _resolve_pipeline_reuse_flags()

    with _STATE.lock:
        _STATE.status = "running"
        _STATE.logs = []
        _STATE.progress = {
            "stage": "starting",
            "detail": "Queued",
            "completed": 0,
            "total": 1,
            "current": 0,
            "count_total": 0,
            "percent": 0.0,
        }

    threading.Thread(
        target=_run_pipeline_worker,
        kwargs={
            "pattern": body.pattern,
            "skip_dataset": skip_dataset,
            "skip_convert": skip_convert,
        },
        daemon=True,
    ).start()

    return {"ok": True, "status": "running"}


@app.get("/reports/html")
def report_html() -> FileResponse:
    """Download the HTML evaluation report."""
    path = get_settings().reports_dir / "evaluation_report.html"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Report not found — run the pipeline first.")
    return FileResponse(path, media_type="text/html")


@app.get("/reports/json")
def report_json() -> FileResponse:
    """Download the JSON evaluation report."""
    path = get_settings().reports_dir / "evaluation_report.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Report not found — run the pipeline first.")
    return FileResponse(path, media_type="application/json", filename="evaluation_report.json")


@app.get("/reports/xlsx")
def report_xlsx() -> FileResponse:
    """Download the Excel evaluation report."""
    path = get_settings().reports_dir / "evaluation_report.xlsx"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Report not found — run the pipeline first.")
    return FileResponse(
        path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename="evaluation_report.xlsx",
    )
