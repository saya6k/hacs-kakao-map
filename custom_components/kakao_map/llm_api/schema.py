"""Shared voluptuous schema pieces for kakao_map LLM tool parameters.

Distinct from ``services.POINT_INPUT``: the HA location *selector* accepts a
bare ``dict`` (whatever shape the frontend UI supplies), but an LLM
function-calling schema needs explicit property names so the model knows to
send ``latitude``/``longitude``.
"""

from __future__ import annotations

import voluptuous as vol
from homeassistant.helpers import config_validation as cv

POINT_INPUT = vol.Any(
    cv.entity_id,
    vol.Schema(
        {
            vol.Required("latitude"): vol.Coerce(float),
            vol.Required("longitude"): vol.Coerce(float),
        }
    ),
)
