# 🛡️ Vimar By-me Alarm for Home Assistant

A standalone Home Assistant custom integration for the **Vimar By-me SAI anti-intrusion system**, communicating locally through a **Vimar 01946 Web Server**.

> [!IMPORTANT]
> This is an independent community project. It is **not an official Vimar integration** and is not affiliated with or endorsed by Vimar.

## ✨ What it does

`vimar_alarm` focuses only on the By-me anti-intrusion system, so it can live next to an existing Vimar Home Assistant integration without recreating lights, covers, climate devices, scenes, or other entities.

### ✅ Verified alarm control

- 🧩 Automatically discovers Vimar SAI partializations
- 🚨 Creates one `alarm_control_panel` per real partialization
- 🏠 Adds an aggregate alarm panel for **all partializations**
- 🔢 Uses Home Assistant's numeric keypad for the SAI PIN
- 🔐 Validates the PIN and its partialization grants before every command
- 🟢 Arms one partialization or all partializations
- ⚪ Disarms one partialization or all partializations
- ✅ Confirms the real state after every command instead of using optimistic state
- 🔒 Does **not** store the SAI PIN in the integration configuration

### 📡 Passive TCP push

The integration listens passively on Vimar TCP port `45211`.

It never sends application data on that socket. TCP is used for local push updates and contact state changes while periodic polling remains a fallback for alarm state refresh.

### 🪟 Contact inputs

The integration discovers physical Vimar SAI **2-input contact interfaces** from the Web Server database and creates two `binary_sensor` entities per interface:

```text
Contact <address> Input 1
Contact <address> Input 2
```

Contact state is received from the passive TCP stream and decoded as a two-bit mask:

| Raw state | Input 1 | Input 2 |
|---|---|---|
| `00` | closed | closed |
| `01` | open | closed |
| `02` | closed | open |
| `03` | open | open |

The physical address is intentionally kept technical and generic. The integration does **not** store room/window mappings in the repository.

#### Recommended first-time contact mapping

Keep the alarm **disarmed**.

For each physical 2-input module, the safest way to identify the two Home Assistant entities is:

1. Start with the two contacts connected to that module **closed**, when practical.
2. Open only one window/door and observe which input changes from closed to open.
3. Close it again and verify the same input returns to closed.
4. Repeat with the second window/door.
5. Rename the two entities in Home Assistant after both channels have been verified.

This avoids confusing the initial combined state of a two-input module. If both contacts are already open, the raw module state can be `03`, so both Home Assistant inputs correctly appear open but that state alone does not tell you which physical opening corresponds to Input 1 versus Input 2.

After the channels have been identified, normal open/close changes are reflected independently through the two bit values.

## 🧠 Verified Vimar protocol

The initial protocol implementation was verified on:

- **Vimar Web Server:** `01946`
- **Firmware:** `2.11`

Observed behavior:

| Function | Vimar Web Server operation |
|---|---|
| Discover partializations | Read-only SQL against the Web Server database |
| Read partialization state | Child `state` object |
| Disarmed | `state = 1` |
| Armed | `state = 2` |
| Validate SAI PIN | `service-vimarsaigetusergrants` |
| Read PIN permissions | `partializationgrants` bit mask |
| Arm | `service-runonelement` → `SETVALUE`, payload `2` |
| Disarm | `service-runonelement` → `SETVALUE`, payload `1` |
| Push/contact stream | Receive-only TCP connection to port `45211` |

The SAI PIN entered in Home Assistant is passed only to the authentication/command request and is discarded after the call.

## 🏠 Individual vs aggregate alarm panels

Assume an installation contains two generic partializations:

```text
Partition 1
Partition 2
```

Home Assistant creates the two real panels plus one aggregate panel.

### Individual panel

Arming one individual panel changes only that real Vimar partialization.

### Aggregate panel

The main **Alarm** entity represents all discovered partializations:

| Real state | Aggregate HA state |
|---|---|
| all disarmed | `disarmed` |
| all armed | `armed_away` |
| only some armed | `armed_custom_bypass` |

When arming/disarming the aggregate panel, the PIN is entered **once**. The integration checks that PIN's grants for every requested partialization before sending any `SETVALUE` command.

If one command fails after another partialization has already changed, the integration deliberately does **not** attempt an automatic rollback. It refreshes the real states and reports the resulting partial state instead.

## 🚨 Triggered state without deliberately sounding the siren

The integration does **not** currently invent a `triggered` mapping.

Instead, diagnostics can read existing Vimar SAI history from `DPADD_BYME_LOG` using `SELECT` only. The diagnostics include technical event IDs/types and numeric device/zone references while avoiding user-defined names where possible.

This allows historical investigation without deliberately triggering an audible alarm test.

## 🧩 Why a separate integration?

This project intentionally uses its own Home Assistant domain:

```text
vimar_alarm
```

You can keep an existing Vimar integration for the rest of the By-me installation and add this one **only for the alarm system**.

No reconfiguration of your existing Vimar lights/covers/climate entities is required.

## 💡 Inspired by

This project exists thanks to the reverse-engineering work and ideas in these projects:

- 🔌 [`h4de5/home-assistant-vimar`](https://github.com/h4de5/home-assistant-vimar) — Vimar Web Server login, SOAP/database approach and TLS compatibility
- 🔔 [`lohacker10/ha-vimar-doorbell`](https://github.com/lohacker10/ha-vimar-doorbell) — passive Vimar 01946 TCP event stream handling and reconnect inspiration

The current alarm implementation is deliberately standalone. See `NOTICE` and `LICENSE` for attribution.

## 📦 Installation with HACS

### Add the custom repository

In Home Assistant:

1. Open **HACS**
2. Open the **⋮** menu
3. Select **Custom repositories**
4. Add:

```text
https://github.com/lohacker10/ha-vimar-byme-alarm
```

5. Select category **Integration**
6. Install **Vimar By-me Alarm**
7. Restart Home Assistant

### Configure the integration

After Home Assistant restarts:

1. Go to **Settings → Devices & services**
2. Click **Add integration**
3. Search for **Vimar By-me Alarm**
4. Enter the Web Server connection details

The **SAI alarm PIN is not configured here**.

## ⬆️ Updating

Update the repository through HACS and restart Home Assistant.

The integration preserves stable unique IDs for existing alarm entities. Contact entities use stable IDs based on the discovered physical address and input number.

## 🧪 Recommended validation

### 1. Test TCP push

Keep the Home Assistant page open and arm/disarm from a **physical Vimar keypad** or the original Web Server.

The HA alarm state should normally refresh faster than the fallback polling interval.

### 2. Identify contact inputs safely

Keep the alarm **disarmed** and use the first-time contact mapping procedure above. Map one physical opening at a time and verify both open and closed states before renaming an entity.

Do not test tamper inputs and do not arm the alarm for this mapping step.

### 3. Test the aggregate panel

Use the main **Alarm** panel:

- arm all partializations with one PIN
- disarm all with one PIN
- arm only one individual panel and verify that the aggregate panel reports a partial/custom-bypass state

### 4. Download diagnostics

Go to the Vimar By-me Alarm integration page, open the config-entry menu and choose **Download diagnostics**.

Diagnostics redact Web Server host, username and password and contain no stored SAI PIN. They deliberately avoid raw TCP payloads and should not contain user-defined partition/zone names in the integration-specific diagnostic sections.

## 🔐 Security

The SAI PIN is:

- ❌ not stored in `configuration.yaml`
- ❌ not stored in the config entry
- ❌ not exposed as an entity attribute
- ❌ intentionally not logged
- ✅ used only during PIN validation and the requested arm/disarm operation

Database access is guarded so that only `SELECT` statements are accepted.

The only intentional state-changing operation is the verified Vimar SAI `SETVALUE` command sent after the user explicitly requests arm/disarm.

The TCP listener is **receive-only** and does not send application data.

> [!WARNING]
> Never attach raw HAR files or unsanitized debug captures to a public issue. They may contain alarm PINs, Web Server credentials, session IDs, cookies, or tokens.

See [`SECURITY.md`](SECURITY.md).

## 👤 Web Server account

Using a **dedicated Vimar Web Server user** for this integration is recommended, especially when another Home Assistant Vimar integration is already connected to the same 01946.

The SAI PIN remains separate from the Web Server login.

## 🚧 Current limitations

- 🚨 `triggered` is not mapped yet
- 🪟 room/window names are not inferred automatically; contacts use generic physical address/input entities
- ⚠️ tamper and fault states are not exposed yet
- 🧪 firmware versions other than those explicitly tested remain unverified

## 🗺️ Roadmap

- 🚨 map `triggered` from verified historical SAI events
- ⚠️ tamper/fault reporting
- 🧠 richer SAI event/log support
- 🪟 optional friendly mapping only if it can be derived generically and safely from protocol/database evidence

## 🐛 Reporting issues

Please include:

- Home Assistant version
- Vimar Web Server model
- Vimar firmware version
- relevant technical contact address/input if needed
- Home Assistant diagnostics when useful

Do **not** include real PINs, passwords, cookies, `sessionid`, SOAP secrets, private LAN addresses, user-defined room names when unnecessary, or raw HAR captures.

Issues: <https://github.com/lohacker10/ha-vimar-byme-alarm/issues>

## 🤝 Contributing

Pull requests are welcome. Please read [`CONTRIBUTING.md`](CONTRIBUTING.md) first.

Protocol changes should state the exact Vimar Web Server model and firmware used for verification.

## 📜 License

This project is distributed under the **GNU General Public License v3.0** because it derives implementation techniques/code from GPL-3.0-licensed `home-assistant-vimar`.

See [`LICENSE`](LICENSE) and [`NOTICE`](NOTICE).

## ❤️ Acknowledgements

Thanks to the maintainers and contributors of:

- `h4de5/home-assistant-vimar`
- `lohacker10/ha-vimar-doorbell`
- Home Assistant
- HACS
