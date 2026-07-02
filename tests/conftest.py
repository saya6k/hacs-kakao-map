"""Shared pytest fixtures for the Kakao Map integration."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Enable loading of the kakao_map custom integration in tests."""
