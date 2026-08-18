# Changelog

## 0.2.0

- Added passive TCP `45211` listener with automatic reconnect.
- TCP traffic is used only as a refresh hint; the Web Server database remains the authoritative state source.
- Added a global alarm panel that arms/disarms all discovered partializations with one SAI PIN.
- Global panel reports `armed_custom_bypass` when only some partializations are armed.
- Added discovery of physical two-input SAI contact interfaces and experimental `binary_sensor` entities.
- Added Home Assistant diagnostics with credential redaction, recent SAI log rows and historical event-class summary.
- Added diagnostics needed to investigate `triggered` without deliberately sounding the siren.
- Increased the default fallback polling interval for new installations to 30 seconds; existing config entries retain their configured interval.

## 0.1.0

- Initial HACS-ready release.
- Standalone `vimar_alarm` integration.
- Automatic SAI partialization discovery.
- One `alarm_control_panel` per partialization.
- Numeric SAI PIN entry through Home Assistant.
- PIN grant validation with `service-vimarsaigetusergrants`.
- Arm/disarm through verified Vimar `SETVALUE` calls.
- Confirmed state polling (`1 = disarmed`, `2 = armed`) on 01946 firmware 2.11.
