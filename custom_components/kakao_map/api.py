"""Client for the official Kakao Local REST API."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from http import HTTPStatus
from typing import Any

import aiohttp

from .const import (
    BIKESET_ROUTE_URL,
    CARS_ROUTE_URL,
    KEYWORD_SEARCH_URL,
    PUBTRANS_ROUTE_URL,
    ROUTE_API_HEADERS,
    TRANSCOORD_URL,
)
from .helpers import ResolvedPoint

_LOGGER = logging.getLogger(__name__)

# Any of these means the best-effort internal route API could not be read; the
# ETA fields degrade to null while the route link is still returned.
_ROUTE_ERRORS = (
    aiohttp.ClientError,
    TimeoutError,
    KeyError,
    IndexError,
    TypeError,
    ValueError,
)


class KakaoApiError(Exception):
    """Base error for Kakao API calls."""


class InvalidApiKey(KakaoApiError):
    """The REST API key was rejected (HTTP 401)."""


class KakaoLocalApi:
    """Async client for dapi.kakao.com Local endpoints."""

    def __init__(self, session: aiohttp.ClientSession, api_key: str) -> None:
        """Store the shared session and the Kakao REST API key."""
        self._session = session
        self._api_key = api_key

    async def async_search_keyword(self, query: str) -> list[dict[str, Any]]:
        """Search places by keyword and return raw documents."""
        headers = {"Authorization": f"KakaoAK {self._api_key}"}
        async with asyncio.timeout(10):
            resp = await self._session.get(
                KEYWORD_SEARCH_URL, params={"query": query}, headers=headers
            )
        if resp.status == HTTPStatus.UNAUTHORIZED:
            raise InvalidApiKey
        resp.raise_for_status()
        data = await resp.json()
        return data["documents"]

    async def async_transcoord(self, longitude: float, latitude: float) -> tuple[int, int]:
        """Convert a WGS84 lng/lat to WCONGNAMUL (x, y) for internal route APIs."""
        headers = {"Authorization": f"KakaoAK {self._api_key}"}
        params: dict[str, str | float] = {
            "x": longitude,
            "y": latitude,
            "input_coord": "WGS84",
            "output_coord": "WCONGNAMUL",
        }
        async with asyncio.timeout(10):
            resp = await self._session.get(TRANSCOORD_URL, params=params, headers=headers)
        resp.raise_for_status()
        data = await resp.json()
        doc = data["documents"][0]
        return int(doc["x"]), int(doc["y"])


@dataclass(slots=True, frozen=True)
class RouteResult:
    """A resolved route's duration (seconds) and distance (meters)."""

    duration: int
    distance: int


@dataclass(slots=True, frozen=True)
class TransitResult:
    """A public-transit route's duration/distance plus transfers and fare."""

    duration: int
    distance: int
    transfers: int
    fare: int


class KakaoMapRouteApi:
    """Best-effort client for map.kakao.com internal route endpoints (no API key)."""

    def __init__(self, session: aiohttp.ClientSession, local_api: KakaoLocalApi) -> None:
        """Store the shared session and the Local API used for coord conversion."""
        self._session = session
        self._local = local_api

    async def async_get_car_route(
        self,
        origin: ResolvedPoint,
        destination: ResolvedPoint,
        waypoints: list[ResolvedPoint],
    ) -> RouteResult | None:
        """Query cars.json for a car route, or None if the internal API fails."""
        params = {
            "origin": self._point_param(origin),
            "destination": self._point_param(destination),
            "priority": "RECOMMEND",
            "roadside": "true",
        }
        if waypoints:
            params["waypoints"] = "|".join(self._point_param(p) for p in waypoints)
        try:
            async with asyncio.timeout(10):
                resp = await self._session.get(
                    CARS_ROUTE_URL, params=params, headers=ROUTE_API_HEADERS
                )
            resp.raise_for_status()
            data = await resp.json(content_type=None)
            route = data[0]
            if route["resultCode"] != "SUCCESS":
                raise ValueError(f"resultCode={route['resultCode']}")
            summary = route["summary"]
            return RouteResult(
                duration=int(summary["duration"]), distance=int(summary["distance"])
            )
        except _ROUTE_ERRORS as err:
            _LOGGER.warning("Kakao car route lookup failed, ETA unavailable: %s", err)
            return None

    async def async_get_bike_route(
        self, origin: ResolvedPoint, destination: ResolvedPoint
    ) -> RouteResult | None:
        """Query bikeset.json for a bicycle route, or None if the internal API fails."""
        try:
            params = await self._wcongnamul_params(origin, destination)
            async with asyncio.timeout(10):
                resp = await self._session.get(
                    BIKESET_ROUTE_URL, params=params, headers=ROUTE_API_HEADERS
                )
            resp.raise_for_status()
            data = await resp.json(content_type=None)
            if data["resultCode"] != "SUCCESS":
                raise ValueError(f"resultCode={data['resultCode']}")
            direction = data["directions"][0]
            return RouteResult(
                duration=int(direction["time"]), distance=int(direction["length"])
            )
        except _ROUTE_ERRORS as err:
            _LOGGER.warning("Kakao bike route lookup failed, ETA unavailable: %s", err)
            return None

    async def async_get_transit_route(
        self, origin: ResolvedPoint, destination: ResolvedPoint
    ) -> TransitResult | None:
        """Query pubtrans.json for the representative transit route, or None on failure."""
        try:
            params = await self._wcongnamul_params(origin, destination)
            async with asyncio.timeout(10):
                resp = await self._session.get(
                    PUBTRANS_ROUTE_URL, params=params, headers=ROUTE_API_HEADERS
                )
            resp.raise_for_status()
            data = await resp.json(content_type=None)
            if data["in_local_status"] != "SUCCESS":
                raise ValueError(f"in_local_status={data['in_local_status']}")
            route = data["in_local"]["routes"][0]
            return TransitResult(
                duration=int(route["time"]["value"]),
                distance=int(route["distance"]["value"]),
                transfers=int(route["transfers"]),
                fare=int(route["fare"]["value"]),
            )
        except _ROUTE_ERRORS as err:
            _LOGGER.warning("Kakao transit route lookup failed, ETA unavailable: %s", err)
            return None

    async def _wcongnamul_params(
        self, origin: ResolvedPoint, destination: ResolvedPoint
    ) -> dict[str, int]:
        """Transcoord both endpoints to WCONGNAMUL sX/sY/eX/eY query params."""
        sx, sy = await self._local.async_transcoord(origin.longitude, origin.latitude)
        ex, ey = await self._local.async_transcoord(
            destination.longitude, destination.latitude
        )
        return {"sX": sx, "sY": sy, "eX": ex, "eY": ey}

    @staticmethod
    def _point_param(point: ResolvedPoint) -> str:
        """Format a point as the `lng,lat,name=…` component cars.json expects."""
        return f"{point.longitude},{point.latitude},name={point.name}"
