# Changelog

## 0.4.1

- Added a deep read-only `sai_alarm_history_probe` over up to 500 SAI rows from `DPADD_BYME_LOG`, retaining every `EVENT_TYPE` because alarm/tamper/restore semantics are still unverified.
- Added `sai_event_context_summary`, an all-history aggregation by event type, message, zone, partialization and device context so rare older alarm-related events remain visible even when they fall outside the newest 500 rows.
- Kept the existing current-state probes and legacy recent/nonstandard event views for comparison.
- Diagnostics continue to omit user-defined display-name columns and redact credentials; the SAI PIN remains transient.
- No `triggered`, tamper, fault, restore, or alarm-memory semantics are assigned yet.
- No changes to arm/disarm behavior, multi-partition `SYNCDB` sequencing, contact decoding, database write policy, or TCP receive-only behavior.

## 0.4.0

- Added a bounded, read-only inventory of SAI-related `DPADD_OBJECT` current-state candidates for triggered/tamper/fault investigation.
- Added a read-only probe for current values of `STATUS_ID` targets referenced by SAI objects.
- Diagnostics now include explicit A/B/C/D/E Walk-test snapshot labels to make before/during/after comparisons reproducible.
- No `triggered`, tamper, fault, restore, or alarm-memory semantics are assigned yet; the release is diagnostic only.
- No changes to arm/disarm behavior, PIN handling, multi-partition `SYNCDB` sequencing, contact decoding, or TCP receive-only behavior.
- Database access remains guarded as `SELECT`-only; user-defined names and Web Server credentials remain redacted from diagnostics.

## 0.3.4

- Confirmed the generic two-input TCP bitmask with a full live sequence: `00` = both closed, `01` = Input 1 open, `02` = Input 2 open, `03` = both open.
- Documented a safer first-time contact mapping procedure: start with both contacts closed when practical, then test one physical opening at a time before renaming entities.
- Updated the README to describe current v0.3.x behavior instead of the older v0.2 experimental contact model.
- Removed installation-specific room/partition examples from public documentation and the development handoff.
- Hardened Home Assistant diagnostics by redacting user-defined/object name fields while preserving technical numeric IDs, physical addresses, raw state values and sanitized TCP contact fields.
- Web Server credentials remain redacted, the SAI PIN remains transient, raw TCP payloads remain disabled, and TCP remains receive-only.

## 0.3.3

- Added sanitized two-byte TCP contact diagnostics for DB-discovered SAI contact modules.
- Diagnostics now retain only address, byte 1, byte 2 and timestamps; raw TCP payloads remain disabled.
- Transition tracking now detects changes in either of the two parsed bytes.
- Existing binary-sensor behavior remains unchanged in this diagnostic release.
- No installation-specific room mapping is stored in the public repository.

## 0.3.2

- Create both generic input entities at setup for every DB-discovered SAI two-input contact module.
- Contact entities no longer require a prior TCP state transition before appearing in Home Assistant.
- TCP remains the live state source; entities may initially be `unknown` until the first frame for their module is received.
- Kept two-bit contact decoding from v0.3.1: bit `0x01` = Input 1, bit `0x02` = Input 2.
- No room-specific names or installation-specific mappings are stored in the public repository.
- Alarm control behavior and the receive-only TCP transport are unchanged.

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
