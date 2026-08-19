"""Diagnostics for Vimar By-me Alarm."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from . import VimarAlarmConfigEntry

_TO_REDACT = {CONF_HOST, CONF_USERNAME, CONF_PASSWORD}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: VimarAlarmConfigEntry,
) -> dict[str, Any]:
    """Return PIN-free, credential-redacted SAI diagnostics."""
    runtime = entry.runtime_data

    recent_events = await hass.async_add_executor_job(
        runtime.api.get_recent_sai_events, 100
    )
    nonstandard_events = await hass.async_add_executor_job(
        runtime.api.get_nonstandard_sai_events, 200
    )
    event_summary = await hass.async_add_executor_job(
        runtime.api.get_sai_event_summary
    )
    logical_zone_values = await hass.async_add_executor_job(
        runtime.api.get_logical_zone_values
    )

    return {
        "entry_data": async_redact_data(dict(entry.data), _TO_REDACT),
        "partitions": [
            {
                "object_id": partition.object_id,
                "name": partition.name,
                "index_id": partition.index_id,
                "status_id": partition.status_id,
                "raw_state": runtime.coordinator.data.partition_states.get(
                    partition.object_id
                ),
            }
            for partition in runtime.partitions
        ],
        "logical_zones": [
            {
                "object_id": zone.object_id,
                "name": zone.name,
                "index_id": zone.index_id,
                "partition_object_id": zone.partition_object_id,
            }
            for zone in runtime.logical_zones
        ],
        "logical_zone_values": logical_zone_values,
        "contact_inputs": [
            {
                "interface_object_id": contact.interface_object_id,
                "channel_object_id": contact.channel_object_id,
                "device_address": contact.device_address,
                "input_number": contact.input_number,
                "raw_state": runtime.coordinator.data.contact_states.get(
                    contact.channel_object_id
                ),
            }
            for contact in runtime.contact_inputs
        ],
        "tcp_push": runtime.tcp_listener.diagnostics(),
        # Deliberately omit ZONE_NAME/PARTIALIZATION_NAME/DEVICE_NAME from logs.
        "recent_sai_events": recent_events,
        "nonstandard_sai_events": nonstandard_events,
        "sai_event_summary": event_summary,
        "notes": {
            "triggered_mapping": (
                "not implemented until a historical event class is verified"
            ),
            "contact_mapping": (
                "physical BYMEFBGO values were observed static on the "
                "development 01946; logical-zone raw values are included "
                "for read-only investigation"
            ),
            "pin_persisted": False,
        },
    }
