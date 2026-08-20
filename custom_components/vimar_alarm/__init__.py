"""Vimar By-me Alarm integration."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_TIMEOUT,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from .api import (
    VimarAlarmApi,
    VimarAlarmAuthError,
    VimarAlarmConnectionError,
    VimarContactInput,
    VimarLogicalZone,
    VimarPartition,
)
from .const import (
    CONF_SCAN_INTERVAL,
    CONF_VERIFY_SSL,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_TCP_PORT,
    DEFAULT_TIMEOUT,
    DEFAULT_VERIFY_SSL,
    PLATFORMS,
)
from .coordinator import VimarAlarmCoordinator
from .tcp import VimarTcpListener


@dataclass(slots=True)
class VimarAlarmRuntime:
    api: VimarAlarmApi
    coordinator: VimarAlarmCoordinator
    partitions: list[VimarPartition]
    contact_inputs: list[VimarContactInput]
    logical_zones: list[VimarLogicalZone]
    tcp_listener: VimarTcpListener


type VimarAlarmConfigEntry = ConfigEntry[VimarAlarmRuntime]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VimarAlarmConfigEntry,
) -> bool:
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
        contact_inputs = await hass.async_add_executor_job(api.get_contact_inputs)
        logical_zones = await hass.async_add_executor_job(api.get_logical_zones)
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
        contact_inputs,
        entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
    )
    await coordinator.async_config_entry_first_refresh()

    def on_tcp_data() -> None:
        hass.loop.call_soon_threadsafe(coordinator.async_push_hint)

    contact_addresses = {
        contact.device_address
        for contact in contact_inputs
        if contact.device_address
    }
    tcp_listener = VimarTcpListener(
        entry.data[CONF_HOST],
        DEFAULT_TCP_PORT,
        on_tcp_data,
        contact_addresses=contact_addresses,
    )

    entry.runtime_data = VimarAlarmRuntime(
        api=api,
        coordinator=coordinator,
        partitions=partitions,
        contact_inputs=contact_inputs,
        logical_zones=logical_zones,
        tcp_listener=tcp_listener,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    tcp_listener.start()
    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: VimarAlarmConfigEntry,
) -> bool:
    await hass.async_add_executor_job(entry.runtime_data.tcp_listener.stop)
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
