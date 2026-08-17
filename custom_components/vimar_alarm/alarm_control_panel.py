"""Alarm panel entities for Vimar SAI partializations."""

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
from .const import DOMAIN, STATE_ARMED, STATE_DISARMED
from .coordinator import VimarAlarmCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VimarAlarmConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    runtime = entry.runtime_data
    async_add_entities(
        VimarPartitionAlarm(runtime.coordinator, entry, partition)
        for partition in runtime.partitions
    )


class VimarPartitionAlarm(CoordinatorEntity[VimarAlarmCoordinator], AlarmControlPanelEntity):
    _attr_code_format = CodeFormat.NUMBER
    _attr_code_arm_required = True
    _attr_supported_features = AlarmControlPanelEntityFeature.ARM_AWAY
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: VimarAlarmCoordinator,
        entry: VimarAlarmConfigEntry,
        partition: VimarPartition,
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self.partition = partition
        self._attr_name = partition.name
        self._attr_unique_id = f"{entry.data['host']}_sai_partition_{partition.object_id}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Vimar By-me Alarm",
            manufacturer="Vimar",
            model="01946 By-me Web Server",
            configuration_url=f"https://{entry.data['host']}",
        )

    @property
    def alarm_state(self) -> AlarmControlPanelState | None:
        value = self.coordinator.data.get(self.partition.object_id)
        if value == STATE_DISARMED:
            return AlarmControlPanelState.DISARMED
        if value == STATE_ARMED:
            return AlarmControlPanelState.ARMED_AWAY
        return None

    @property
    def extra_state_attributes(self) -> dict[str, int | str]:
        return {
            "vimar_object_id": self.partition.object_id,
            "vimar_status_id": self.partition.status_id,
            "vimar_partition_index": self.partition.index_id,
            "vimar_raw_state": self.coordinator.data.get(self.partition.object_id, ""),
        }

    async def _async_set(self, armed: bool, code: str | None) -> None:
        try:
            # The PIN lives only in this call stack and in the outgoing SOAP request.
            await self.hass.async_add_executor_job(
                lambda: self._entry.runtime_data.api.set_partition_state(
                    self.partition, armed=armed, pin=code
                )
            )
        except VimarAlarmInvalidPin as err:
            raise HomeAssistantError("PIN SAI Vimar non valido") from err
        except VimarAlarmPermissionError as err:
            raise HomeAssistantError(
                "Il PIN SAI non è autorizzato per questa parzializzazione"
            ) from err
        except VimarAlarmEnrollmentError as err:
            raise HomeAssistantError("Enrollment SAI Vimar non completato") from err
        except VimarAlarmCommandError as err:
            raise HomeAssistantError(str(err)) from err

        await self.coordinator.async_request_refresh()

    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        await self._async_set(True, code)

    async def async_alarm_disarm(self, code: str | None = None) -> None:
        await self._async_set(False, code)
