# Codex Handoff — Vimar By-me Alarm

## Goal

Continue development of `lohacker10/ha-vimar-byme-alarm`, a standalone Home Assistant custom integration for the Vimar By-me SAI/anti-intrusion system through a Vimar 01946 Web Server.

The integration must remain separate from the existing general-purpose Vimar integration so users do not need to recreate lights, covers, climate devices, etc.

## Verified hardware / protocol baseline

Development and live validation were performed against:

- Vimar Web Server: `01946`
- Firmware: `2.11`
- Home Assistant custom integration domain: `vimar_alarm`

Do not assume unverified firmware versions behave identically.

## Security constraints

Treat this as alarm/security software.

- Never persist or log the SAI PIN.
- Never expose the SAI PIN as an entity attribute or diagnostics value.
- Web Server username/password are normal integration credentials, but must be redacted from diagnostics.
- Never log SOAP bodies that can contain `<pin>`, `<hashcode>`, `<sessionid>`, cookies, passwords or tokens.
- Database access must remain `SELECT`-only. The SQL guard must fail closed.
- The only intentional state-changing operation is the explicit SAI arm/disarm `SETVALUE` requested by the user.
- TCP port `45211` is receive-only. Do not send application data to it.
- Do not implement optimistic alarm state. Re-read the Web Server state after commands.
- Do not invent alarm/trigger/tamper semantics without captured evidence.

## Verified Vimar SAI behavior

### Partializations

The Web Server database exposes SAI partializations under:

`_DPAD_VIMAR_SAI_PARTITIONS_CONTAINER`

The test installation has two real partializations:

- `INGR` — partition index 1
- `GARAGE` — partition index 2

Each partialization has a child object named `state`.

Verified state mapping on firmware 2.11:

- `state = 1` → disarmed
- `state = 2` → armed

This mapping was captured while GARAGE was manually armed and disarmed and then validated by live Home Assistant tests.

### SAI PIN authentication

The Web Server UI validates a 5-digit SAI PIN through SOAP service:

`service-vimarsaigetusergrants`

The successful response includes `partializationgrants`, a bit mask of which partializations the PIN may control.

The PIN must be supplied transiently for each requested command; it must not be stored in the config entry.

### Arm / disarm

The Web Server UI uses `service-runonelement` on the partialization object itself:

- operation: `SETVALUE`
- arm payload: `2`
- disarm payload: `1`
- callsource: `WEB`
- the transient SAI PIN is passed as the Vimar `hashcode`

The integration must validate the PIN/grants first and then verify the resulting database state after the command.

## v0.1 validation status

The user completed the requested v0.1 live tests successfully:

- discovery of INGR and GARAGE works
- both entities survive Home Assistant restart
- arm/disarm from Home Assistant works
- correct SAI PIN works
- incorrect PIN is rejected without changing state
- state changes made from the physical Vimar side are reflected by polling
- integration recovers from normal use without reconfiguration

The existing unique IDs of the INGR and GARAGE entities should remain stable across upgrades.

## v0.2 design / implementation

The approved v0.2 direction contains four independent modules.

### 1. Passive TCP push trigger

Use TCP port `45211` only as a passive event trigger.

Architecture:

`TCP recv event -> request coordinator refresh -> authoritative DB SELECT -> update entities`

Do not decode a TCP frame directly into alarm state yet. The database remains authoritative.

Keep periodic polling as fallback. TCP reconnect must be resilient and should never block Home Assistant shutdown.

### 2. Physical contact inputs as binary sensors

The diagnostic DB dump shows five physical `SAIInterfacciaContatti__2In` interfaces, each with two feedback channels, so there are up to ten physical contact inputs.

Known logical contact names seen in the Web Server DB include:

- `CONTATTI 1 ENTRATA`
- `CONTATTI CAMERETTA`
- `CONTATTI 3 CAMERA`
- `CONTATTI CUCINA`
- `CONTATTI GARAGE`

The user also has contacts for two bathrooms; those names were not visible in the initial logical-object dump.

Therefore physical channels should initially have technical stable names/unique IDs, for example:

`Vimar SAI Contact <address> Input <n>`

The user can identify the two bathroom channels safely by opening/closing one window at a time while the alarm is disarmed.

Current expected raw mapping is:

- `0` → closed/rest
- `1` → open

Only `0` has already been observed at rest. Confirm `1` from a real open/close test before treating it as universally verified.

Use Home Assistant `binary_sensor` with an opening/window-appropriate device class.

### 3. Aggregate alarm entity

In addition to INGR and GARAGE, expose a third aggregate alarm entity representing all real partializations.

State semantics:

- all disarmed → `disarmed`
- all armed → `armed_away`
- mixed armed/disarmed → `armed_custom_bypass`

Command behavior:

- ask for the PIN once
- validate grants for every target partition before issuing writes
- arm/disarm only the partitions that need a state change
- verify all real states afterward
- do not automatically rollback if a later partition command fails; expose the actual mixed state and return an error

This mirrors the Vimar Web Server/tastierino user experience where the user enters one PIN and then selects one, several, or all partializations.

### 4. Read-only SAI history diagnostics

The Web Server UI reads the SAI history table:

`DPADD_BYME_LOG`

Useful fields include:

- `TIMESTAMP`
- `ZONE_ID`
- `ZONE_NUMBER`
- `ZONE_NAME`
- `PARTIALIZATION_ID`
- `PARTIALIZATION_NUMBER`
- `PARTIALIZATION_NAME`
- `DEVICE_ID`
- `DEVICE_ADDRESS`
- `DEVICE_NAME`
- `MESSAGE`
- `EVENT_TYPE`
- `CATEGORY`

Use read-only history diagnostics to look for old intrusion/alarm events before asking the user to generate a new alarm.

The user explicitly does not want to deliberately trigger the audible sirens.

Do not map Home Assistant `triggered` until a real historical/captured event gives enough evidence to identify the exact alarm-start and alarm-clear semantics.

## Triggered state strategy

Preferred order:

1. inspect historical `DPADD_BYME_LOG` events in read-only mode
2. correlate historical message/event types with known SAI alarm trigger objects
3. if sufficient evidence exists, implement `triggered`
4. otherwise leave it unimplemented until a natural real event occurs

Do not recommend disabling sirens, modifying Vimar alarm programming, firmware, or security configuration merely to force a test.

## Existing inspiration / attribution

The integration is inspired by and derives transport/TLS ideas from:

- `h4de5/home-assistant-vimar`
- `lohacker10/ha-vimar-doorbell`

The project remains GPL-3.0 compatible. Preserve `LICENSE` and `NOTICE` attribution.

Important upstream lesson: current `home-assistant-vimar` recognizes `CH_SAI` objects but classifies them as unsupported. This integration intentionally supports only the alarm subset rather than forking/replacing all Vimar functionality.

## Home Assistant design principles

- Prefer `DataUpdateCoordinator` for authoritative state refreshes.
- Keep the general integration local-only.
- Preserve stable entity unique IDs.
- Use config flow; do not ask for the SAI PIN during setup.
- Use Home Assistant alarm code handling so the PIN is supplied only with arm/disarm service calls.
- Diagnostics must redact secrets.
- Keep Italian and English translations.
- HACS compatibility must remain intact.

## Testing priorities after v0.2 is installed

1. Confirm TCP listener connects and physical keypad arm/disarm produces near-immediate HA refresh.
2. With the alarm disarmed, open/close one known window and identify which physical binary sensor toggles.
3. Map all contact channels, including both bathrooms, without arming the alarm.
4. Test aggregate entity:
   - GARAGE only armed → aggregate `armed_custom_bypass`
   - INGR + GARAGE armed via aggregate → aggregate `armed_away`
   - aggregate disarm → both return to `disarmed`
5. Download sanitized Home Assistant diagnostics and inspect historical SAI events for possible `triggered` mapping.

## Do not expose private data

No real values for the following belong in this repository:

- private LAN IP addresses
- Web Server username/password
- SAI PIN
- SOAP session IDs
- cookies
- raw unsanitized HAR/network captures
- personal filesystem paths

## First task for Codex

Read this file, `README.md`, `custom_components/vimar_alarm/api.py`, `coordinator.py`, `alarm_control_panel.py`, `binary_sensor.py`, `tcp.py`, and `diagnostics.py` before modifying anything.

Then run repository-level validation and review the v0.2 implementation for Home Assistant API correctness, concurrency/shutdown safety, secret handling, and HACS/hassfest compatibility. Preserve the verified Vimar protocol behavior above unless new captured evidence contradicts it.
