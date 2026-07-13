"""Thin llm.API shell for kakao_map, registered once at component setup.

Deliberately kept outside the `llm/` platform package and does not import
`homeassistant.components.llm` at module scope: doing so would force our
tool modules to import at kakao_map setup time instead of on the first LLM
request, defeating HA's lazy platform loading (see `llm/__init__.py`). The
one call that needs `homeassistant.components.llm` is deferred into
`async_get_api_instance`, which only ever runs once that integration exists
and has requested an instance.
"""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers import llm

from .const import API_NAME, DOMAIN


class KakaoMapAPI(llm.API):
    """Exposes kakao_map's tools by aggregating the `llm` platform hooks."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize with kakao_map's stable API id."""
        super().__init__(hass=hass, id=DOMAIN, name=API_NAME)

    async def async_get_api_instance(self, llm_context: llm.LLMContext) -> llm.APIInstance:
        """Return the instance of the API."""
        from homeassistant.components.llm import (  # noqa: PLC0415
            async_get_tools as async_get_platform_tools,
        )

        llm_tools = await async_get_platform_tools(self.hass, llm_context, self.id)
        return llm.APIInstance(
            api=self,
            api_prompt=llm_tools.prompt or "",
            llm_context=llm_context,
            tools=llm_tools.tools,
        )
