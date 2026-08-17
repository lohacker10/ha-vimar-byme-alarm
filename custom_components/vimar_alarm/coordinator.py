"""Coordinator for Vimar By-me Alarm."""

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntryAuthFailed
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import VimarAlarmApi, VimarAlarmAuthError, VimarAlarmConnectionError, VimarPartition
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class VimarAlarmCoordinator(DataUpdateCoordinator[dict[int, str]]):
    def __init__(
        self,
        hass: HomeAssistant,
        api: VimarAlarmApi,
        partitions: list[VimarPartition],
        scan_interval: int,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
            always_update=False,
        )
        self.api = api
        self.partitions = partitions

    async def _async_update_data(self) -> dict[int, str]:
        try:
            return await self.hass.async_add_executor_job(
                self.api.get_partition_states, self.partitions
            )
        except VimarAlarmAuthError as err:
            raise ConfigEntryAuthFailed("Vimar Web Server authentication failed") from err
        except VimarAlarmConnectionError as err:
            raise UpdateFailed(str(err)) from err
