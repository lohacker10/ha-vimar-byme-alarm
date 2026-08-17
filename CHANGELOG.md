# Changelog

## 0.1.0

- Initial HACS-ready release.
- Standalone `vimar_alarm` integration.
- Automatic SAI partialization discovery.
- One `alarm_control_panel` per partialization.
- Numeric SAI PIN entry through Home Assistant.
- PIN grant validation with `service-vimarsaigetusergrants`.
- Arm/disarm through verified Vimar `SETVALUE` calls.
- Confirmed state polling (`1 = disarmed`, `2 = armed`) on 01946 firmware 2.11.
