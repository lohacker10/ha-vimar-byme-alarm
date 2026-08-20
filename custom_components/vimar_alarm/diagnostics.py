"""Diagnostics for Vimar By-me Alarm."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from . import VimarAlarmConfigEntry

_TO_REDACT = {CONF_HOST, CONF_USERNAME, CONF_PASSWORD}


def _redact_user_names(value: Any) -> Any:
    """Remove user-defined/object names while retaining technical IDs and values."""
    if isinstance(value, list):
        return [_redact_user_names(item) for item in value]
    if not isinstance(value, dict):
        return value

    redacted: dict[str, Any] = {}
    for key, item in value.items():
        normalized = str(key).lower()
        if normalized == "name" or normalized.endswith("_name"):
            redacted[key] = "**REDACTED**"
        else:
            redacted[key] = _redact_user_names(item)
    return redacted


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: VimarAlarmConfigEntry,
) -> dict[str, Any]:
    """Return PIN-free, credential- and user-name-redacted SAI diagnostics."""
    runtime = entry.runtime_data

    recent_events = await hass.async_add_executor_job(runtime.api.get_recent_sai_events, 100)
    nonstandard_events = await hass.async_add_executor_job(runtime.api.get_nonstandard_sai_events, 200)
    sai_alarm_history_probe = await hass.async_add_executor_job(runtime.api.get_sai_alarm_history_probe, 500)
    sai_event_context_summary = await hass.async_add_executor_job(runtime.api.get_sai_event_context_summary)
    event_summary = await hass.async_add_executor_job(runtime.api.get_sai_event_summary)
    logical_zone_values = await hass.async_add_executor_job(runtime.api.get_logical_zone_values)
    sai_current_state_probe = await hass.async_add_executor_job(runtime.api.get_sai_current_state_probe)
    sai_status_target_probe = await hass.async_add_executor_job(runtime.api.get_sai_status_target_probe)
    sai_relation_probe = await hass.async_add_executor_job(runtime.api.get_sai_relation_probe)
    sai_incoming_relation_probe = await hass.async_add_executor_job(runtime.api.get_sai_incoming_relation_probe)
    sai_status_link_probe = await hass.async_add_executor_job(runtime.api.get_sai_status_link_probe)

    diagnostics = {
        "entry_data": async_redact_data(dict(entry.data), _TO_REDACT),
        "partitions": [
            {
                "object_id": partition.object_id,
                "index_id": partition.index_id,
                "status_id": partition.status_id,
                "raw_state": runtime.coordinator.data.partition_states.get(partition.object_id),
                "triggered": runtime.coordinator.is_partition_triggered(partition.object_id),
            }
            for partition in runtime.partitions
        ],
        "logical_zones": [
            {
                "object_id": zone.object_id,
                "index_id": zone.index_id,
                "partition_object_id": zone.partition_object_id,
            }
            for zone in runtime.logical_zones
        ],
        "logical_zone_values": logical_zone_values,
        "sai_current_state_probe": sai_current_state_probe,
        "sai_status_target_probe": sai_status_target_probe,
        "sai_relation_probe": sai_relation_probe,
        "sai_incoming_relation_probe": sai_incoming_relation_probe,
        "sai_status_link_probe": sai_status_link_probe,
        "contact_inputs": [
            {
                "interface_object_id": contact.interface_object_id,
                "channel_object_id": contact.channel_object_id,
                "device_address": contact.device_address,
                "input_number": contact.input_number,
                "raw_state": runtime.coordinator.data.contact_states.get(contact.channel_object_id),
            }
            for contact in runtime.contact_inputs
        ],
        "tcp_push": runtime.tcp_listener.diagnostics(),
        "intrusion_tracking": runtime.coordinator.intrusion_diagnostics(),
        "recent_sai_events": recent_events,
        "nonstandard_sai_events": nonstandard_events,
        "sai_alarm_history_probe": sai_alarm_history_probe,
        "sai_event_context_summary": sai_event_context_summary,
        "sai_event_summary": event_summary,
        "notes": {
            "diagnostic_release": "0.5.0",
            "triggered_mapping": "verified historical intrusion EVENT_TYPE values 70, 71 and 83; latched per partialization until disarm",
            "future_intrusion_validation": "after any natural or controlled intrusion, download diagnostics and inspect intrusion_tracking.recent_intrusion_events plus recent_processed_events",
            "power_event_mapping": "historical correlation: EVENT_TYPE 58 = mains failure, EVENT_TYPE 82 = mains restore; not exposed as entities yet",
            "startup_behavior": "existing historical events are baselined and cannot retrigger Home Assistant after restart",
            "sai_alarm_history_probe": "up to 500 SAI log rows from DPADD_BYME_LOG, newest first",
            "sai_event_context_summary": "all-history grouping of SAI events by technical class, zone, partition and device context",
            "contact_mapping": "TCP state byte is a verified two-bit mask: 0x01 = Input 1, 0x02 = Input 2",
            "pin_persisted": False,
            "database_write_enabled": False,
            "tcp_application_writes_enabled": False,
            "user_defined_names_redacted": True,
        },
    }

    return _redact_user_names(diagnostics)
