"""Resolve get_directions point inputs (entity selector or coordinates) to WGS84.

Follows the pattern of the HERE / Waze / Google travel-time integrations: a point
is either an entity holding latitude/longitude attributes or an explicit
coordinate pair, resolved at call time. Unlike their `find_coordinates` helper,
failures raise a ServiceValidationError naming the exact input at fault.
"""

from __future__ import annotations

from dataclasses import dataclass

import voluptuous as vol
from homeassistant.const import ATTR_FRIENDLY_NAME, ATTR_LATITUDE, ATTR_LONGITUDE
from homeassistant.core import HomeAssistant, valid_entity_id
from homeassistant.exceptions import ServiceValidationError

from .const import DOMAIN

COORDS_SCHEMA = vol.All([vol.Coerce(float)], vol.Length(min=2, max=2))


@dataclass(slots=True, frozen=True)
class ResolvedPoint:
    """A route point resolved to a display name and WGS84 coordinates."""

    name: str
    latitude: float
    longitude: float


def _is_number(value: str) -> bool:
    """Return True if the whole string parses as a float."""
    try:
        float(value)
    except ValueError:
        return False
    return True


def _resolve_entity(hass: HomeAssistant, entity_id: str) -> ResolvedPoint:
    """Resolve an entity_id to its coordinate attributes and friendly name."""
    state = hass.states.get(entity_id)
    if state is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="entity_not_found",
            translation_placeholders={"entity_id": entity_id},
        )
    latitude = state.attributes.get(ATTR_LATITUDE)
    longitude = state.attributes.get(ATTR_LONGITUDE)
    if not isinstance(latitude, int | float) or not isinstance(longitude, int | float):
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="entity_missing_coordinates",
            translation_placeholders={"entity_id": entity_id},
        )
    name = state.attributes.get(ATTR_FRIENDLY_NAME) or entity_id
    return ResolvedPoint(name=name, latitude=float(latitude), longitude=float(longitude))


def resolve_point(
    hass: HomeAssistant,
    *,
    role: str,
    entity_id: str | None = None,
    coords: object = None,
) -> ResolvedPoint:
    """Resolve one origin/destination input given as entity XOR [lat, lon] coords."""
    if entity_id is not None and coords is not None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="point_input_conflict",
            translation_placeholders={"role": role},
        )
    if entity_id is not None:
        return _resolve_entity(hass, entity_id)
    if coords is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="point_input_missing",
            translation_placeholders={"role": role},
        )
    try:
        latitude, longitude = COORDS_SCHEMA(coords)
    except vol.Invalid as err:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="invalid_coords",
            translation_placeholders={"role": role, "value": str(coords)},
        ) from err
    return ResolvedPoint(name=role, latitude=latitude, longitude=longitude)


def resolve_waypoint(hass: HomeAssistant, value: str, *, index: int) -> ResolvedPoint:
    """Resolve one waypoint entry given as an entity_id or a "lat,lon" string."""
    if "," in value:
        parts = [part.strip() for part in value.split(",")]
        if len(parts) == 2:
            try:
                latitude, longitude = (float(parts[0]), float(parts[1]))
            except ValueError:
                pass
            else:
                return ResolvedPoint(name=f"경유지{index}", latitude=latitude, longitude=longitude)
    elif valid_entity_id(value) and not _is_number(value):
        return _resolve_entity(hass, value)
    raise ServiceValidationError(
        translation_domain=DOMAIN,
        translation_key="invalid_waypoint",
        translation_placeholders={"value": value},
    )
