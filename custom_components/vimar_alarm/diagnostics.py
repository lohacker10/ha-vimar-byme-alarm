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
    event_summary = await hass.async_add_executor_job(runtime.api.get_sai_event_summary)

    return {
        "entry_data": async_redact_data(dict(entry.data), _TO_REDACT),
        "partitions": [
            {
                "object_id": p.object_id,
                "name": p.name,
                "index_id": p.index_id,
                "status_id": p.status_id,
                "raw_state": runtime.coordinator.data.partition_states.get(p.object_id),
            }
            for p in runtime.partitions
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
        "contact_inputs": [
            {
                "interface_object_id": c.interface_object_id,
                "channel_object_id": c.channel_object_id,
                "device_address": c.device_address,
                "input_number": c.input_number,
                "raw_state": runtime.coordinator.data.contact_states.get(
                    c.channel_object_id
                ),
            }
            for c in runtime.contact_inputs
        ],
        "tcp_push": runtime.tcp_listener.diagnostics(),
        # Deliberately omit ZONE_NAME/PARTIALIZATION_NAME/DEVICE_NAME from log rows.
        "recent_sai_events": recent_events,
        "sai_event_summary": event_summary,
        "notes": {
            "triggered_mapping": "not implemented until a historical event class is verified",
            "contact_mapping": "physical channels are experimental; identify with alarm disarmed",
            "pin_persisted": False,
        },
    }
