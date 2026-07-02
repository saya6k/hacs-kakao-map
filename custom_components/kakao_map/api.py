"""Client for the official Kakao Local REST API."""

from __future__ import annotations

import asyncio
from http import HTTPStatus
from typing import Any

import aiohttp

from .const import KEYWORD_SEARCH_URL


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
