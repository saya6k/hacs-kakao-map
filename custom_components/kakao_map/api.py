"""Client for the official Kakao Local REST API."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from http import HTTPStatus
from typing import Any

import aiohttp

from .const import CARS_ROUTE_URL, KEYWORD_SEARCH_URL, ROUTE_API_HEADERS
from .helpers import ResolvedPoint

_LOGGER = logging.getLogger(__name__)


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


@dataclass(slots=True, frozen=True)
class RouteResult:
    """A resolved route's duration (seconds) and distance (meters)."""

    duration: int
    distance: int


class KakaoMapRouteApi:
    """Best-effort client for map.kakao.com internal route endpoints (no API key)."""

    def __init__(self, session: aiohttp.ClientSession) -> None:
        """Store the shared session."""
        self._session = session

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
        except (
            aiohttp.ClientError,
            TimeoutError,
            KeyError,
            IndexError,
            TypeError,
            ValueError,
        ) as err:
            _LOGGER.warning("Kakao car route lookup failed, ETA unavailable: %s", err)
            return None

    @staticmethod
    def _point_param(point: ResolvedPoint) -> str:
        """Format a point as the `lng,lat,name=…` component cars.json expects."""
        return f"{point.longitude},{point.latitude},name={point.name}"
