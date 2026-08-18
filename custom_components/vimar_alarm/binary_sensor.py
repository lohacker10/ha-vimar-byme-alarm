"""Experimental raw SAI contact inputs for Vimar By-me Alarm."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import VimarAlarmConfigEntry
from .api import VimarContactInput
from .const import DOMAIN
from .coordinator import VimarAlarmCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VimarAlarmConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create one binary sensor for each physical SAI contact input."""
    runtime = entry.runtime_data
    async_add_entities(
        VimarRawContactBinarySensor(runtime.coordinator, entry, contact)
        for contact in runtime.contact_inputs
    )


class VimarRawContactBinarySensor(
    CoordinatorEntity[VimarAlarmCoordinator], BinarySensorEntity
):
    """Raw input of a Vimar SAI two-input contact interface.

    The v0.2 discovery deliberately uses physical input names because the supplied
    firmware dump does not contain a verified mapping for every room/window name.
    Opening/closing windows while the alarm is DISARMED can be used to identify
    and rename the entities safely in Home Assistant.
    """

    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.OPENING

    def __init__(
        self,
        coordinator: VimarAlarmCoordinator,
        entry: VimarAlarmConfigEntry,
        contact: VimarContactInput,
    ) -> None:
        super().__init__(coordinator)
        self.contact = contact
        self._entry = entry
        self._attr_name = f"Input {contact.input_number}"
        self._attr_unique_id = (
            f"{entry.data['host']}_sai_contact_"
            f"{contact.interface_object_id}_{contact.channel_object_id}"
        )
        self._attr_device_info = DeviceInfo(
            identifiers={
                (DOMAIN, f"{entry.entry_id}_contact_{contact.interface_object_id}")
            },
            name=f"Vimar SAI Contact {contact.device_address}",
            manufacturer="Vimar",
            model="SAI 2-input contact interface",
            via_device=(DOMAIN, entry.entry_id),
        )

    @property
    def is_on(self) -> bool | None:
        """0 was observed with all tested contacts at rest/closed.

        Only exact 0/1 values are exposed. Anything else remains unknown rather
        than guessing a security-relevant contact state.
        """
        raw = self.coordinator.data.contact_states.get(self.contact.channel_object_id)
        if raw == "0":
            return False
        if raw == "1":
            return True
        return None

    @property
    def extra_state_attributes(self) -> dict[str, int | str]:
        return {
            "vimar_interface_object_id": self.contact.interface_object_id,
            "vimar_channel_object_id": self.contact.channel_object_id,
            "vimar_device_address": self.contact.device_address,
            "vimar_input_number": self.contact.input_number,
            "vimar_raw_state": self.coordinator.data.contact_states.get(
                self.contact.channel_object_id, ""
            ),
            "mapping_status": "experimental",
        }
