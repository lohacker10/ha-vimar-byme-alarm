# Changelog

## 0.3.1

- Fixed TCP contact decoding for Vimar SAI 2-input contact interfaces.
- Each confirmed physical contact module now exposes two generic binary sensors: `Contact <address> Input 1` and `Contact <address> Input 2`.
- TCP contact state is decoded as a two-bit mask: bit `0x01` drives Input 1 and bit `0x02` drives Input 2.
- Raw TCP state remains available as an entity attribute for diagnostics.
- No room-specific names or installation-specific mappings are stored in the public repository.
- Alarm control behavior, PIN validation, TCP receive-only handling, and multi-partition `SYNCDB` sequencing are unchanged.

## 0.3.0

- Added generic TCP-backed SAI contact binary sensors.
- A contact entity is created only after a DB-known physical contact address shows a real TCP state transition.
- Contact entities use generic names such as `Contact 0029`; no room-specific mapping is stored in the public repository.
- Contact state mapping uses verified TCP values `00 = closed` and `02 = open`; raw state remains available as an entity attribute.
- Alarm and contact entities now share one Home Assistant device named `Vimar Alarm`.
- Alarm entity display names are now `Alarm`, `Alarm <partialization>` without the previous `Vimar By-me` prefix.
- Existing alarm control behavior, PIN validation, TCP push, and the validated multi-partition `SYNCDB` sequence are unchanged.
- The TCP socket remains receive-only and raw payloads are never exposed in diagnostics.

## 0.2.4

- Added passive TCP contact diagnostics parser.
- TCP remains receive-only; raw payloads are never exposed in diagnostics.
- Added contact frame state hints using only address/state metadata.
- No changes to arm/disarm, multi-partition SYNCDB sequence, or contact entities.

## 0.2.3

- Added read-only diagnostics that inspect outgoing and incoming `DPADD_OBJECT_RELATION` links around logical SAI zones and physical two-input contact interfaces.
- Added a read-only status-link probe for objects whose `STATUS_ID` points at a SAI zone/interface.
- Contact entities remain unchanged; the new probes are only for identifying the authoritative live contact state source before changing entity behavior.
- No changes to arm/disarm, the validated multi-partition `SYNCDB` sequence, or TCP push.

## 0.2.2

- Fixed multi-partition arm/disarm to mirror the Vimar 01946 Web Server sequence captured on firmware 2.11.
- Multi-partition commands are sent in descending SAI partialization index order.
- Every command in a multi-partition batch except the final one uses `SYNCDB`; the final command uses `NO-OPTIONALS`.
- Single-partition commands remain unchanged and continue to use `NO-OPTIONALS`.
- No changes to TCP push, contact entities, or triggered-state mapping.

## 0.2.1

- Expanded read-only diagnostics for contact-state investigation.
- Logical SAI zones now include their raw database `CURRENT_VALUE` in diagnostics.
- Added historical non-standard SAI event rows (`EVENT_TYPE` other than 0/1) to diagnostics so alarm/tamper/fault classes can be investigated without deliberately triggering the siren.
- Kept arm/disarm, aggregate-panel behavior, TCP push, and physical contact entities unchanged while their remaining protocol semantics are investigated.

## 0.2.0

- Added passive TCP `45211` listener with automatic reconnect.
- TCP traffic is used only as a refresh hint; the Web Server database remains the authoritative state source.
- Added a global alarm panel that arms/disarms all discovered partializations with one SAI PIN.
- Global panel reports `armed_custom_bypass` when only some partializations are armed.
- Added discovery of physical two-input SAI contact interfaces and experimental `binary_sensor` entities.
- Added Home Assistant diagnostics with credential redaction, recent SAI log rows and historical event-class summary.
- Added diagnostics needed to investigate `triggered` without deliberately sounding the siren.

## 0.1.0

- Initial HACS-ready release.
