"""Vendored subset of Home Assistant core's own test helpers.

pytest-homeassistant-custom-component (phacc) is mechanically generated from
one specific released HA version (see its `ha_version` file) and breaks
against HA's `dev` branch — an unrelated `http` component refactor removed a
symbol phacc's own autouse `disable_http_server` fixture patches, so *every*
test fails at setup regardless of content. See tasks/plan.md T13 for the full
investigation.

This package vendors just the pieces of HA core's tests/common.py and
tests/test_util/aiohttp.py that this repo's test suite actually needs, copied
from a pinned `dev`-branch commit, so tests can run against a pre-release HA
build. Delete this package and go back to importing from
pytest_homeassistant_custom_component once it ships a release tracking
HA > 2026.7.2.
"""
