"""Vendored from home-assistant/core tests/common.py.

Source: https://github.com/home-assistant/core/blob/9cd694008baf1222fc3815f9c0d9303dc583c46f/tests/common.py
(dev branch, 2026-07-10). Only `async_test_home_assistant` and the
`MockConfigEntry` constructor + `add_to_hass` are kept — trimmed to what this
repo's tests actually use. Refresh from the same URL (swap the commit) when
re-pinning to a newer dev snapshot.

Two changes from upstream: `config_dir` is required (upstream's
`get_test_config_dir()` default depends on a `tests/testing_config/` fixture
tree we don't vendor), and `MockConfigEntry` drops the reauth/reconfigure-flow
helpers this repo's tests don't call.
"""

from __future__ import annotations

import asyncio
import functools as ft
import os
from collections.abc import AsyncGenerator, Mapping, Sequence
from contextlib import asynccontextmanager, suppress
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

from homeassistant import auth, config_entries, loader
from homeassistant.auth import auth_store
from homeassistant.const import EVENT_HOMEASSISTANT_CLOSE, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import CoreState, HomeAssistant, callback
from homeassistant.helpers import (
    area_registry as ar,
)
from homeassistant.helpers import (
    category_registry as cr,
)
from homeassistant.helpers import (
    condition,
    entity,
    storage,
    translation,
    trigger,
)
from homeassistant.helpers import (
    device_registry as dr,
)
from homeassistant.helpers import (
    entity_registry as er,
)
from homeassistant.helpers import (
    floor_registry as fr,
)
from homeassistant.helpers import (
    issue_registry as ir,
)
from homeassistant.helpers import (
    label_registry as lr,
)
from homeassistant.helpers import (
    restore_state as rs,
)
from homeassistant.util import dt as dt_util
from homeassistant.util import ulid as ulid_util
from homeassistant.util.async_ import _SHUTDOWN_RUN_CALLBACK_THREADSAFE
from homeassistant.util.unit_system import METRIC_SYSTEM

INSTANCES: list[HomeAssistant] = []


class StoreWithoutWriteLoad[T: (Mapping[str, Any] | Sequence[Any])](storage.Store[T]):
    """Fake store that does not write or load. Used for testing."""

    async def async_save(self, *args: Any, **kwargs: Any) -> None:
        """Save the data. Mocked out in tests."""

    @callback
    def async_save_delay(self, *args: Any, **kwargs: Any) -> None:
        """Save data with an optional delay. Mocked out in tests."""


def ensure_auth_manager_loaded(auth_mgr: auth.AuthManager) -> None:
    """Ensure an auth manager is considered loaded."""
    store = auth_mgr._store
    if store._users is None:
        store._set_defaults()


@asynccontextmanager
async def async_test_home_assistant(
    event_loop: Any = None,
    load_registries: bool = True,
    *,
    config_dir: str,
    initial_state: CoreState = CoreState.running,
) -> AsyncGenerator[HomeAssistant]:
    """Return a Home Assistant object pointing at a test config dir."""
    hass = HomeAssistant(config_dir)
    store = auth_store.AuthStore(hass)
    hass.auth = auth.AuthManager(hass, store, {}, {})
    ensure_auth_manager_loaded(hass.auth)
    INSTANCES.append(hass)

    orig_async_add_job = hass.async_add_job
    orig_async_add_executor_job = hass.async_add_executor_job
    orig_async_create_task_internal = hass.async_create_task_internal
    orig_tz = dt_util.get_default_time_zone()

    def async_add_job(target, *args, eager_start: bool = False):
        """Add job."""
        check_target = target
        while isinstance(check_target, ft.partial):
            check_target = check_target.func

        if isinstance(check_target, Mock) and not isinstance(target, AsyncMock):
            fut = asyncio.Future()
            fut.set_result(target(*args))
            return fut

        return orig_async_add_job(target, *args, eager_start=eager_start)

    def async_add_executor_job(target, *args):
        """Add executor job."""
        check_target = target
        while isinstance(check_target, ft.partial):
            check_target = check_target.func

        if isinstance(check_target, Mock):
            fut = asyncio.Future()
            fut.set_result(target(*args))
            return fut

        return orig_async_add_executor_job(target, *args)

    def async_create_task_internal(coroutine, name=None, eager_start=True):
        """Create task."""
        if isinstance(coroutine, Mock) and not isinstance(coroutine, AsyncMock):
            fut = asyncio.Future()
            fut.set_result(None)
            return fut

        return orig_async_create_task_internal(coroutine, name, eager_start)

    hass.async_add_job = async_add_job
    hass.async_add_executor_job = async_add_executor_job
    hass.async_create_task_internal = async_create_task_internal

    hass.data[loader.DATA_CUSTOM_COMPONENTS] = {}

    hass.config.location_name = "test home"
    hass.config.latitude = 32.87336
    hass.config.longitude = -117.22743
    hass.config.elevation = 0
    await hass.config.async_set_time_zone("US/Pacific")
    hass.config.units = METRIC_SYSTEM
    hass.config.media_dirs = {"local": os.path.join(config_dir, "media")}
    hass.config.skip_pip = True
    hass.config.skip_pip_packages = []

    hass.config_entries = config_entries.ConfigEntries(
        hass,
        {
            "_": (
                "Not empty or else some bad checks for hass config in discovery.py"
                " breaks"
            )
        },
    )
    hass.bus.async_listen_once(
        EVENT_HOMEASSISTANT_STOP,
        hass.config_entries._async_shutdown,
    )

    # Load the registries
    entity.async_setup(hass)
    loader.async_setup(hass)
    await condition.async_setup(hass)
    await trigger.async_setup(hass)

    hass.data[translation.TRANSLATION_FLATTEN_CACHE] = translation._TranslationCache(hass)
    if load_registries:
        dr.async_setup(hass)

        with (
            patch.object(StoreWithoutWriteLoad, "async_load", return_value=None),
            patch(
                "homeassistant.helpers.area_registry.AreaRegistryStore",
                StoreWithoutWriteLoad,
            ),
            patch(
                "homeassistant.helpers.device_registry.DeviceRegistryStore",
                StoreWithoutWriteLoad,
            ),
            patch(
                "homeassistant.helpers.entity_registry.EntityRegistryStore",
                StoreWithoutWriteLoad,
            ),
            patch(
                "homeassistant.helpers.storage.Store",
                StoreWithoutWriteLoad,
            ),
            patch(
                "homeassistant.helpers.issue_registry.IssueRegistryStore",
                StoreWithoutWriteLoad,
            ),
            patch(
                "homeassistant.helpers.restore_state.RestoreStateData.async_setup_dump",
                return_value=None,
            ),
            patch(
                "homeassistant.helpers.restore_state.start.async_at_start",
            ),
        ):
            await ar.async_load(hass)
            await cr.async_load(hass)
            await dr.async_load(hass)
            await er.async_load(hass)
            await fr.async_load(hass)
            await ir.async_load(hass)
            await lr.async_load(hass)
            await rs.async_load(hass)

    hass.set_state(initial_state)

    @callback
    def clear_instance(event):
        """Clear global instance."""
        hass.loop.call_soon(INSTANCES.remove, hass)

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_CLOSE, clear_instance)

    try:
        yield hass
    finally:
        dt_util.set_default_time_zone(orig_tz)
        with suppress(AttributeError):
            delattr(hass.loop, _SHUTDOWN_RUN_CALLBACK_THREADSAFE)


class MockConfigEntry(config_entries.ConfigEntry):
    """Helper for creating config entries that adds some defaults."""

    def __init__(
        self,
        *,
        data=None,
        disabled_by=None,
        discovery_keys=None,
        domain="test",
        entry_id=None,
        minor_version=1,
        options=None,
        pref_disable_new_entities=None,
        pref_disable_polling=None,
        reason=None,
        source=config_entries.SOURCE_USER,
        state=None,
        subentries_data=None,
        title="Mock Title",
        unique_id=None,
        version=1,
    ) -> None:
        """Initialize a mock config entry."""
        discovery_keys = discovery_keys or {}
        kwargs = {
            "data": data or {},
            "disabled_by": disabled_by,
            "discovery_keys": discovery_keys,
            "domain": domain,
            "entry_id": entry_id or ulid_util.ulid_now(),
            "minor_version": minor_version,
            "options": options or {},
            "pref_disable_new_entities": pref_disable_new_entities,
            "pref_disable_polling": pref_disable_polling,
            "subentries_data": subentries_data or (),
            "title": title,
            "unique_id": unique_id,
            "version": version,
        }
        if source is not None:
            kwargs["source"] = source
        if state is not None:
            kwargs["state"] = state
        super().__init__(**kwargs)
        if reason is not None:
            object.__setattr__(self, "reason", reason)

    def add_to_hass(self, hass: HomeAssistant) -> None:
        """Test helper to add entry to hass."""
        hass.config_entries._entries[self.entry_id] = self
