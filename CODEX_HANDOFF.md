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
- Do not store installation-specific room names, private addresses, personal paths or physical-address-to-room mappings in the public repository.

## Verified Vimar SAI behavior

### Partializations

The Web Server database exposes SAI partializations under:

`_DPAD_VIMAR_SAI_PARTITIONS_CONTAINER`

Each partialization has a child object named `state`.

Verified state mapping on firmware 2.11:

- `state = 1` → disarmed
- `state = 2` → armed

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

For multiple partializations, preserve the verified sequencing behavior already implemented: commands are sent in descending partialization index order, every command except the last uses `SYNCDB`, and the final command uses `NO-OPTIONALS`.

## Passive TCP push

Use TCP port `45211` only as a passive receive-only stream.

The integration uses the stream for push refreshes and live contact states. Do not introduce outbound application frames.

Periodic polling remains a fallback for authoritative alarm state refreshes.

## Physical 2-input contact modules

The Web Server database exposes physical `SAIInterfacciaContatti__2In` interfaces. Each discovered physical module produces two generic Home Assistant binary sensors:

`Contact <address> Input 1`

`Contact <address> Input 2`

Do not hardcode installation-specific physical addresses or room names.

### Verified TCP state encoding

For the contact frame format currently parsed by `tcp.py`, the first state byte is a two-bit mask:

- `00` → both inputs closed
- `01` → Input 1 open, Input 2 closed
- `02` → Input 1 closed, Input 2 open
- `03` → both inputs open

Input 1 uses mask `0x01`; Input 2 uses mask `0x02`.

The following byte changes with the state and appears to be a frame check/control value. It is retained only as a sanitized diagnostic field and must not be used as contact state unless future evidence requires it.

### Contact mapping procedure

For first-time physical identification, keep the alarm disarmed. When practical, start with both contacts on a two-input module closed, then open/close one physical contact at a time and verify which generic input changes. Repeat for the second contact before renaming entities in Home Assistant.

If both contacts start open, the raw module state may already be `03`, which correctly marks both inputs open but does not identify which physical opening is Input 1 versus Input 2.

## Aggregate alarm entity

Expose one aggregate alarm entity representing all discovered real partializations.

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

## Read-only SAI history diagnostics

The Web Server UI reads the SAI history table:

`DPADD_BYME_LOG`

Use read-only history diagnostics to investigate old intrusion/alarm events before asking for a new alarm event.

Do not map Home Assistant `triggered` until a real historical/captured event gives enough evidence to identify exact alarm-start and alarm-clear semantics.

Diagnostics should prefer technical numeric IDs/addresses and omit user-defined names wherever those names are not required for debugging.

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

## Home Assistant design principles

- Prefer `DataUpdateCoordinator` for authoritative alarm state refreshes.
- Keep the general integration local-only.
- Preserve stable entity unique IDs.
- Use config flow; do not ask for the SAI PIN during setup.
- Use Home Assistant alarm code handling so the PIN is supplied only with arm/disarm service calls.
- Diagnostics must redact secrets and avoid unnecessary installation-specific names.
- Keep Italian and English translations.
- HACS compatibility must remain intact.

## Do not expose private data

No real values for the following belong in this repository:

- private LAN IP addresses
- Web Server username/password
- SAI PIN
- SOAP session IDs
- cookies
- raw unsanitized HAR/network captures
- personal filesystem paths
- installation-specific room/window names or address-to-room mappings

## First task for Codex

Read this file, `README.md`, `custom_components/vimar_alarm/api.py`, `coordinator.py`, `alarm_control_panel.py`, `binary_sensor.py`, `tcp.py`, and `diagnostics.py` before modifying anything.

Then run repository-level validation and review the implementation for Home Assistant API correctness, concurrency/shutdown safety, secret handling, and HACS/hassfest compatibility. Preserve verified Vimar protocol behavior unless new captured evidence contradicts it.
