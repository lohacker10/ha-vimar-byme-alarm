"""Coordinator for Vimar By-me Alarm."""

from __future__ import annotations

from collections import deque
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
from .const import DOMAIN, INTRUSION_EVENT_TYPES, STATE_DISARMED

_LOGGER = logging.getLogger(__name__)


class VimarAlarmCoordinator(DataUpdateCoordinator[VimarStateSnapshot]):
    """Poll Vimar state and track verified intrusion events."""

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
            # Event-log changes can alter triggered state even when DB state is unchanged.
            always_update=True,
        )
        self.api = api
        self.partitions = partitions
        self.contact_inputs = contact_inputs
        self._push_refresh_pending = False
        self._event_cursor: int | None = None
        self._triggered_partitions: set[int] = set()
        self._recent_processed_events: deque[dict[str, str]] = deque(maxlen=30)
        self._recent_intrusion_events: deque[dict[str, str]] = deque(maxlen=20)

    @property
    def triggered_partitions(self) -> frozenset[int]:
        """Return partializations currently latched as triggered."""
        return frozenset(self._triggered_partitions)

    def is_partition_triggered(self, partition_object_id: int) -> bool:
        """Return whether one partialization is currently latched as triggered."""
        return partition_object_id in self._triggered_partitions

    @staticmethod
    def _event_int(event: dict[str, str], key: str, default: int = -1) -> int:
        try:
            return int(event.get(key, str(default)))
        except (TypeError, ValueError):
            return default

    def _process_events(
        self,
        events: list[dict[str, str]],
        snapshot: VimarStateSnapshot,
    ) -> None:
        known_partition_ids = {partition.object_id for partition in self.partitions}

        for event in events:
            event_id = self._event_int(event, "ID", 0)
            if event_id > 0:
                self._event_cursor = max(self._event_cursor or 0, event_id)

            sanitized = {
                key: event.get(key, "")
                for key in (
                    "ID",
                    "TIMESTAMP",
                    "ZONE_ID",
                    "ZONE_NUMBER",
                    "PARTIALIZATION_ID",
                    "PARTIALIZATION_NUMBER",
                    "DEVICE_ID",
                    "DEVICE_ADDRESS",
                    "MESSAGE",
                    "EVENT_TYPE",
                    "CATEGORY",
                )
            }
            self._recent_processed_events.append(sanitized)

            event_type = self._event_int(event, "EVENT_TYPE")
            partition_id = self._event_int(event, "PARTIALIZATION_ID")
            if event_type not in INTRUSION_EVENT_TYPES:
                continue
            if partition_id not in known_partition_ids:
                continue

            self._recent_intrusion_events.append(sanitized)
            # A newly observed verified intrusion event latches the affected
            # partialization. If it has already been disarmed by this refresh,
            # the clear step below immediately releases the latch while the
            # event remains available in diagnostics.
            self._triggered_partitions.add(partition_id)

        for partition_id in tuple(self._triggered_partitions):
            if snapshot.partition_states.get(partition_id) == STATE_DISARMED:
                self._triggered_partitions.discard(partition_id)

    async def _async_update_data(self) -> VimarStateSnapshot:
        try:
            snapshot = await self.hass.async_add_executor_job(
                self.api.get_state_snapshot,
                self.partitions,
                self.contact_inputs,
            )

            if self._event_cursor is None:
                # Baseline at startup so old retained alarm events can never
                # make Home Assistant appear triggered after a restart.
                self._event_cursor = await self.hass.async_add_executor_job(
                    self.api.get_latest_sai_event_id
                )
            else:
                events = await self.hass.async_add_executor_job(
                    self.api.get_sai_events_after,
                    self._event_cursor,
                    500,
                )
                self._process_events(events, snapshot)

            # Disarm is the verified user/system action that clears the local
            # intrusion latch. Keep this check even when no new log row exists.
            for partition_id in tuple(self._triggered_partitions):
                if snapshot.partition_states.get(partition_id) == STATE_DISARMED:
                    self._triggered_partitions.discard(partition_id)

            return snapshot
        except VimarAlarmAuthError as err:
            raise ConfigEntryAuthFailed("Vimar Web Server authentication failed") from err
        except VimarAlarmConnectionError as err:
            raise UpdateFailed(str(err)) from err

    def intrusion_diagnostics(self) -> dict[str, object]:
        """Return privacy-safe evidence for future intrusion validation."""
        return {
            "verified_event_types": sorted(INTRUSION_EVENT_TYPES),
            "event_cursor": self._event_cursor,
            "triggered_partition_object_ids": sorted(self._triggered_partitions),
            "recent_processed_events": list(self._recent_processed_events),
            "recent_intrusion_events": list(self._recent_intrusion_events),
            "startup_baseline_prevents_historical_retrigger": True,
            "clear_policy": "latch clears when affected partialization is disarmed",
        }

    @callback
    def async_push_hint(self) -> None:
        """Debounce TCP notifications and refresh authoritative DB state/event log."""
        if self._push_refresh_pending:
            return
        self._push_refresh_pending = True
        self.hass.loop.call_later(0.35, self._async_start_push_refresh)

    @callback
    def _async_start_push_refresh(self) -> None:
        self._push_refresh_pending = False
        self.hass.async_create_task(self.async_request_refresh())
