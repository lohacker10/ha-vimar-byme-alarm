"""Coordinator for Vimar By-me Alarm."""

from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntryAuthFailed
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    VimarAlarmApi,
    VimarAlarmAuthError,
    VimarAlarmConnectionError,
    VimarContactInput,
    VimarPartition,
    VimarStateSnapshot,
)
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class VimarAlarmCoordinator(DataUpdateCoordinator[VimarStateSnapshot]):
    """Poll Vimar state, with TCP events acting only as refresh hints."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: VimarAlarmApi,
        partitions: list[VimarPartition],
        contact_inputs: list[VimarContactInput],
        scan_interval: int,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=max(5, scan_interval)),
            always_update=False,
        )
        self.api = api
        self.partitions = partitions
        self.contact_inputs = contact_inputs
        self._push_refresh_pending = False

    async def _async_update_data(self) -> VimarStateSnapshot:
        try:
            return await self.hass.async_add_executor_job(
                self.api.get_state_snapshot,
                self.partitions,
                self.contact_inputs,
            )
        except VimarAlarmAuthError as err:
            raise ConfigEntryAuthFailed("Vimar Web Server authentication failed") from err
        except VimarAlarmConnectionError as err:
            raise UpdateFailed(str(err)) from err

    @callback
    def async_push_hint(self) -> None:
        """Debounce TCP notifications and refresh authoritative DB state."""
        if self._push_refresh_pending:
            return
        self._push_refresh_pending = True
        self.hass.loop.call_later(0.35, self._async_start_push_refresh)

    @callback
    def _async_start_push_refresh(self) -> None:
        self._push_refresh_pending = False
        self.hass.async_create_task(self.async_request_refresh())
