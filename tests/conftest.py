"""Shared pytest fixtures and configuration."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _isolate_settings():
    """Reset the cached settings singleton between tests."""
    import src.config as cfg
    cfg._settings = None
    yield
    cfg._settings = None
