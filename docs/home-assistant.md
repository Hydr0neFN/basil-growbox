# Home Assistant integration

The device exposes itself over the ESPHome native API
(`Noise_NNpsk0_25519_ChaChaPoly_SHA256` encryption, key in `secrets.yaml`) to a Raspberry Pi 4
running Home Assistant. It does not run a local web UI or MQTT — HA is the only interface by
design (see the note in `basil.yaml` on why `web_server:` was removed: an ESP8266 serves very
few simultaneous connections, and a browser holding a web UI's SSE stream competes directly
with HA's API session for the same limited slot).

| Domain | Purpose |
|---|---|
| `sensor` | Soil moisture %, soil voltage (diagnostic), tank %, tank depth, tank distance (diagnostic), box temperature, box humidity, WiFi signal, uptime |
| `binary_sensor` | Needs water, tank empty, drain fault |
| `switch` | Grow light (the fill pump is intentionally **not** exposed — an untimed pump switch in someone else's automation is a hazard) |
| `number` | Dose (cm), Max cycles, Stop at (%), Water below (%), Lockout (h) |
| `button` | Water now, Calibrate: start fill, Calibrate: save dose, Clear drain fault |

Three alert automations notify on state change:

- **Drain fault** — fires immediately on latch, links to the clear-fault button.
- **Tank empty** — 5-minute debounce to ride out the transient dip during an active flood.
- **Device offline** — `sensor.basil_uptime` going `unavailable` for 30 minutes, long enough to
  ride out an HA restart or a normal Wi-Fi blip without paging anyone for nothing.
