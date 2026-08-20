"""Alarm panel entities for Vimar SAI partializations."""

from __future__ import annotations

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
    CodeFormat,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import VimarAlarmConfigEntry
from .api import (
    VimarAlarmCommandError,
    VimarAlarmEnrollmentError,
    VimarAlarmInvalidPin,
    VimarAlarmPermissionError,
    VimarPartition,
)
from .const import DOMAIN, INTRUSION_EVENT_TYPES, STATE_ARMED, STATE_DISARMED
from .coordinator import VimarAlarmCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VimarAlarmConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    runtime = entry.runtime_data
    entities: list[AlarmControlPanelEntity] = [
        VimarAllPartitionsAlarm(runtime.coordinator, entry)
    ]
    entities.extend(
        VimarPartitionAlarm(runtime.coordinator, entry, partition)
        for partition in runtime.partitions
    )
    async_add_entities(entities)


class VimarAlarmBase(CoordinatorEntity[VimarAlarmCoordinator], AlarmControlPanelEntity):
    """Shared behavior for Vimar alarm panels."""

    _attr_code_format = CodeFormat.NUMBER
    _attr_code_arm_required = True
    _attr_supported_features = AlarmControlPanelEntityFeature.ARM_AWAY
    _attr_has_entity_name = False

    def __init__(
        self,
        coordinator: VimarAlarmCoordinator,
        entry: VimarAlarmConfigEntry,
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Vimar Alarm",
            manufacturer="Vimar",
            model="01946 By-me Web Server",
            configuration_url=f"https://{entry.data['host']}",
        )

    async def _async_execute(
        self,
        partitions: list[VimarPartition],
        armed: bool,
        code: str | None,
    ) -> None:
        try:
            await self.hass.async_add_executor_job(
                lambda: self._entry.runtime_data.api.set_multiple_partition_states(
                    partitions,
                    armed=armed,
                    pin=code,
                )
            )
        except VimarAlarmInvalidPin as err:
            raise HomeAssistantError("PIN SAI Vimar non valido") from err
        except VimarAlarmPermissionError as err:
            raise HomeAssistantError(
                "Il PIN SAI non è autorizzato per tutte le parzializzazioni richieste"
            ) from err
        except VimarAlarmEnrollmentError as err:
            raise HomeAssistantError("Enrollment SAI Vimar non completato") from err
        except VimarAlarmCommandError as err:
            await self.coordinator.async_request_refresh()
            raise HomeAssistantError(str(err)) from err
        await self.coordinator.async_request_refresh()


class VimarPartitionAlarm(VimarAlarmBase):
    """One real Vimar SAI partialization."""

    def __init__(
        self,
        coordinator: VimarAlarmCoordinator,
        entry: VimarAlarmConfigEntry,
        partition: VimarPartition,
    ) -> None:
        super().__init__(coordinator, entry)
        self.partition = partition
        self._attr_name = f"Alarm {partition.name}"
        self._attr_unique_id = (
            f"{entry.data['host']}_sai_partition_{partition.object_id}"
        )

    @property
    def alarm_state(self) -> AlarmControlPanelState | None:
        if self.coordinator.is_partition_triggered(self.partition.object_id):
            return AlarmControlPanelState.TRIGGERED
        value = self.coordinator.data.partition_states.get(self.partition.object_id)
        if value == STATE_DISARMED:
            return AlarmControlPanelState.DISARMED
        if value == STATE_ARMED:
            return AlarmControlPanelState.ARMED_AWAY
        return None

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        return {
            "vimar_object_id": self.partition.object_id,
            "vimar_status_id": self.partition.status_id,
            "vimar_partition_index": self.partition.index_id,
            "vimar_raw_state": self.coordinator.data.partition_states.get(
                self.partition.object_id, ""
            ),
            "vimar_intrusion_latched": self.coordinator.is_partition_triggered(
                self.partition.object_id
            ),
            "vimar_intrusion_event_types": sorted(INTRUSION_EVENT_TYPES),
        }

    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        await self._async_execute([self.partition], True, code)

    async def async_alarm_disarm(self, code: str | None = None) -> None:
        await self._async_execute([self.partition], False, code)


class VimarAllPartitionsAlarm(VimarAlarmBase):
    """Aggregate panel that arms/disarms every discovered partialization."""

    def __init__(
        self,
        coordinator: VimarAlarmCoordinator,
        entry: VimarAlarmConfigEntry,
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_name = "Alarm"
        self._attr_unique_id = f"{entry.data['host']}_sai_all_partitions"

    @property
    def alarm_state(self) -> AlarmControlPanelState | None:
        if self.coordinator.triggered_partitions:
            return AlarmControlPanelState.TRIGGERED
        states = [
            self.coordinator.data.partition_states.get(partition.object_id)
            for partition in self._entry.runtime_data.partitions
        ]
        if not states or any(
            state not in {STATE_DISARMED, STATE_ARMED} for state in states
        ):
            return None
        if all(state == STATE_DISARMED for state in states):
            return AlarmControlPanelState.DISARMED
        if all(state == STATE_ARMED for state in states):
            return AlarmControlPanelState.ARMED_AWAY
        return AlarmControlPanelState.ARMED_CUSTOM_BYPASS

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        return {
            "partitions": {
                partition.name: self.coordinator.data.partition_states.get(
                    partition.object_id, ""
                )
                for partition in self._entry.runtime_data.partitions
            },
            "triggered_partition_object_ids": sorted(
                self.coordinator.triggered_partitions
            ),
            "vimar_intrusion_event_types": sorted(INTRUSION_EVENT_TYPES),
            "tcp_push_connected": self._entry.runtime_data.tcp_listener.stats.connected,
        }

    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        await self._async_execute(self._entry.runtime_data.partitions, True, code)

    async def async_alarm_disarm(self, code: str | None = None) -> None:
        await self._async_execute(self._entry.runtime_data.partitions, False, code)
