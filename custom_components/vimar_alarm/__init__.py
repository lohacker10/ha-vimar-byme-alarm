"""Vimar By-me Alarm integration."""

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_TIMEOUT, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from .api import VimarAlarmApi, VimarAlarmAuthError, VimarAlarmConnectionError, VimarPartition
from .const import (
    CONF_SCAN_INTERVAL,
    CONF_VERIFY_SSL,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_TIMEOUT,
    DEFAULT_VERIFY_SSL,
    PLATFORMS,
)
from .coordinator import VimarAlarmCoordinator


@dataclass(slots=True)
class VimarAlarmRuntime:
    api: VimarAlarmApi
    coordinator: VimarAlarmCoordinator
    partitions: list[VimarPartition]


type VimarAlarmConfigEntry = ConfigEntry[VimarAlarmRuntime]


async def async_setup_entry(hass: HomeAssistant, entry: VimarAlarmConfigEntry) -> bool:
    api = VimarAlarmApi(
        host=entry.data[CONF_HOST],
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
        port=entry.data.get(CONF_PORT, DEFAULT_PORT),
        verify_ssl=entry.data.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL),
        timeout=entry.data.get(CONF_TIMEOUT, DEFAULT_TIMEOUT),
    )
    try:
        partitions = await hass.async_add_executor_job(api.test_connection)
    except VimarAlarmAuthError as err:
        raise ConfigEntryAuthFailed("Invalid Vimar Web Server credentials") from err
    except VimarAlarmConnectionError as err:
        raise ConfigEntryNotReady(str(err)) from err

    if not partitions:
        raise ConfigEntryNotReady("No Vimar SAI partializations discovered")

    coordinator = VimarAlarmCoordinator(
        hass,
        api,
        partitions,
        entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
    )
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = VimarAlarmRuntime(api, coordinator, partitions)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: VimarAlarmConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
