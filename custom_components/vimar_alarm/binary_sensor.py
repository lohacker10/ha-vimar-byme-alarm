"""TCP-backed generic SAI contact sensors."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import VimarAlarmConfigEntry
from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VimarAlarmConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add two generic input sensors after a DB-known module changes on TCP."""
    runtime = entry.runtime_data
    known_addresses: set[str] = set()

    @callback
    def _add_confirmed_contact(address: str) -> None:
        if address in known_addresses:
            return
        state = runtime.tcp_listener.contact_state(address)
        if state is None or int(state.get("changes", 0)) < 1:
            return
        known_addresses.add(address)
        async_add_entities(
            [
                VimarTcpContactBinarySensor(entry, address, 1, 0x01),
                VimarTcpContactBinarySensor(entry, address, 2, 0x02),
            ]
        )

    for address in runtime.tcp_listener.confirmed_contact_addresses():
        _add_confirmed_contact(address)

    def _on_tcp_contact(address: str, _state: str, _changes: int) -> None:
        hass.loop.call_soon_threadsafe(_add_confirmed_contact, address)

    entry.async_on_unload(runtime.tcp_listener.add_contact_listener(_on_tcp_contact))


class VimarTcpContactBinarySensor(BinarySensorEntity):
    """One input bit of a DB-known SAI two-input contact interface."""

    _attr_should_poll = False
    _attr_has_entity_name = False
    _attr_device_class = BinarySensorDeviceClass.OPENING

    def __init__(
        self,
        entry: VimarAlarmConfigEntry,
        address: str,
        input_number: int,
        input_mask: int,
    ) -> None:
        self._entry = entry
        self._address = address.upper()
        self._input_number = input_number
        self._input_mask = input_mask
        self._remove_listener = None
        self._attr_name = f"Contact {self._address} Input {input_number}"
        self._attr_unique_id = (
            f"{entry.entry_id}_tcp_contact_{self._address}_input_{input_number}"
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Vimar Alarm",
            manufacturer="Vimar",
            model="01946 By-me Web Server",
            configuration_url=f"https://{entry.data['host']}",
        )

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()

        def _on_contact(address: str, _state: str, _changes: int) -> None:
            if address == self._address:
                self.hass.loop.call_soon_threadsafe(self.async_write_ha_state)

        self._remove_listener = (
            self._entry.runtime_data.tcp_listener.add_contact_listener(_on_contact)
        )

    async def async_will_remove_from_hass(self) -> None:
        if self._remove_listener is not None:
            self._remove_listener()
            self._remove_listener = None
        await super().async_will_remove_from_hass()

    @property
    def is_on(self) -> bool | None:
        state = self._entry.runtime_data.tcp_listener.contact_state(self._address)
        if state is None:
            return None
        raw = str(state.get("state", ""))
        try:
            raw_value = int(raw, 16)
        except ValueError:
            return None
        return bool(raw_value & self._input_mask)

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        state = self._entry.runtime_data.tcp_listener.contact_state(self._address) or {}
        return {
            "address": self._address,
            "input": self._input_number,
            "input_mask": f"0x{self._input_mask:02X}",
            "source": "tcp_45211",
            "raw_state": state.get("state", ""),
            "change_count": state.get("changes", 0),
            "last_seen": state.get("last_seen"),
        }
