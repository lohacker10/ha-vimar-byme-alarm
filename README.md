# 🛡️ Vimar By-me Alarm for Home Assistant

A standalone Home Assistant custom integration for the **Vimar By-me SAI anti-intrusion system**, communicating locally through a **Vimar 01946 Web Server**.

> [!IMPORTANT]
> This is an independent community project. It is **not an official Vimar integration** and is not affiliated with or endorsed by Vimar.

## ✨ What it does

`vimar_alarm` focuses only on the By-me anti-intrusion system, so it can live next to an existing Vimar Home Assistant integration without recreating your lights, covers, climate devices, scenes, or other entities.

Current features:

- 🧩 Automatically discovers Vimar SAI partializations
- 🚨 Creates one Home Assistant `alarm_control_panel` per partialization
- 🔢 Uses Home Assistant's numeric keypad for the SAI PIN
- 🔐 Validates the PIN and its partialization grants before every command
- 🟢 Arms a selected partialization
- ⚪ Disarms a selected partialization
- ✅ Confirms the real state after every command instead of using optimistic state
- 🏠 Works entirely on the local network
- 📡 Polls all partialization states with a single read-only database query
- 🔒 Does **not** store the SAI PIN in the integration configuration

On the development system, for example, Home Assistant discovers independent partializations such as `INGR` and `GARAGE`.

## 🧠 How it works

The initial protocol implementation was verified on:

- **Vimar Web Server:** `01946`
- **Firmware:** `2.11`

Observed behavior:

| Function | Vimar Web Server operation |
|---|---|
| Discover partializations | Read-only SQL against the Web Server database |
| Read state | Child `state` object of each partialization |
| Disarmed | `state = 1` |
| Armed | `state = 2` |
| Validate SAI PIN | `service-vimarsaigetusergrants` |
| Read PIN permissions | `partializationgrants` bit mask |
| Arm | `service-runonelement` → `SETVALUE`, payload `2` |
| Disarm | `service-runonelement` → `SETVALUE`, payload `1` |

The SAI PIN entered in Home Assistant is passed only to the authentication/command request and is discarded after the call.

## 🧩 Why a separate integration?

This project intentionally uses its own Home Assistant domain:

```text
vimar_alarm
```

That means you can keep an existing Vimar integration for the rest of the By-me installation and add this one **only for the alarm system**.

No reconfiguration of your existing Vimar lights/covers/climate entities is required.

## 💡 Inspired by

This project exists thanks to the reverse-engineering work and ideas in these projects:

- 🔌 [`h4de5/home-assistant-vimar`](https://github.com/h4de5/home-assistant-vimar) — Vimar Web Server login, SOAP/database approach and TLS compatibility
- 🔔 [`lohacker10/ha-vimar-doorbell`](https://github.com/lohacker10/ha-vimar-doorbell) — passive observation of the Vimar 01946 TCP event stream and inspiration for future push updates

The current alarm implementation is deliberately standalone, but the protocol and transport approach are derived in part from `home-assistant-vimar`. See `NOTICE` and `LICENSE`.

## 📦 Installation with HACS

### 1. Add this repository to HACS

In Home Assistant:

1. Open **HACS**
2. Open the **⋮** menu
3. Select **Custom repositories**
4. Add:

```text
https://github.com/lohacker10/ha-vimar-byme-alarm
```

5. Select category **Integration**
6. Click **Add**
7. Find **Vimar By-me Alarm** in HACS and install it
8. Restart Home Assistant

### 2. Configure the integration

After Home Assistant restarts:

1. Go to **Settings → Devices & services**
2. Click **Add integration**
3. Search for **Vimar By-me Alarm**
4. Enter:
   - Web Server IP/hostname
   - Web Server username
   - Web Server password
   - HTTPS port (normally `443`)
   - SSL verification setting
   - polling interval

The **SAI alarm PIN is not configured here**.

### 3. Arm or disarm

Home Assistant creates one alarm entity per Vimar partialization.

Select the entity you want to control and press **Arm away** or **Disarm**. Home Assistant will ask for the SAI PIN when the command is executed.

## 🧰 Manual installation

Copy:

```text
custom_components/vimar_alarm/
```

to:

```text
/config/custom_components/vimar_alarm/
```

Restart Home Assistant and add the integration from **Settings → Devices & services**.

## 🔐 Security

This integration treats the alarm PIN as sensitive transient data.

The SAI PIN is:

- ❌ not stored in `configuration.yaml`
- ❌ not stored in the config entry
- ❌ not exposed as an entity attribute
- ❌ intentionally not logged
- ✅ used only during PIN validation and the requested arm/disarm operation

Database access is guarded so that only `SELECT` statements are allowed.

The only intentional state-changing operation is the Vimar SAI `SETVALUE` call sent after the user explicitly requests arm/disarm.

> [!WARNING]
> Never attach raw HAR files or debug captures to a public issue. They may contain alarm PINs, Web Server credentials, session IDs, cookies, or tokens.

See [`SECURITY.md`](SECURITY.md).

## 👤 Web Server account

Using a **dedicated Vimar Web Server user** for this integration is recommended, especially when another Home Assistant Vimar integration is already connected to the same 01946.

The SAI PIN remains separate from the Web Server login.

## 🚧 Current limitations

This is an early MVP. The following features are intentionally not guessed yet:

- 🚨 exact `triggered` / alarm-in-progress state mapping
- ⚠️ tamper and fault states
- 🚪 zone/contact entities
- 📡 TCP `45211` push updates
- 🏘️ combined "all partializations" alarm entity
- 🧪 firmware versions other than those explicitly tested

The current implementation maps only the state values that have been verified from real traffic.

## 🗺️ Roadmap

Planned work includes:

- 📡 real-time state updates using the 01946 TCP event stream
- 🚨 triggered alarm state
- ⚠️ tamper/fault reporting
- 🚪 zone and sensor status
- 🧠 richer SAI event/log support
- 🏠 optional aggregate alarm entity

## 🧪 Compatibility

Currently verified against **Vimar 01946 firmware 2.11**.

Other firmware versions may use the same protocol, but they should be considered unverified until tested.

## 🐛 Reporting issues

Please include:

- Home Assistant version
- Vimar Web Server model
- Vimar firmware version
- partialization involved
- sanitized logs

Do **not** include real PINs, passwords, cookies, `sessionid`, SOAP secrets, or raw HAR captures.

Issues:  
`https://github.com/lohacker10/ha-vimar-byme-alarm/issues`

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

Reverse engineering local protocols is much easier when the community documents what it learns.
