**English** · [繁體中文](README.zh-TW.md)

# Basil grow-box: closed-loop ebb-and-flow irrigation on an ESP8266

Indoor basil, zero natural light, bottom-watered by a pump that reads the soil instead of a timer.

![The grow-box: a terracotta pot of basil seedlings sitting in the mouth of a translucent plastic bucket reservoir, the pot rim wrapped in perforated aluminium foil as a fungus-gnat barrier, under four ring-light lamps on gooseneck stalks clamped to a shelf edge. To the left, a NodeMCU ESP8266 on perfboard with an SSD1306 OLED and a blue 4-channel relay module. Below the shelf, a black tub holding a second board on its lid. The OLED reads 12:41, SOIL 100%, TANK -0.0%, 28.0 C 65% RH.](docs/img/rig-hero.jpg)

*The rig as built, 2026-09-20. The foil around the pot is a fungus-gnat barrier, not a seal —
see [why perforation still works](docs/watering.md#fungus-gnat-control-part-2-perforated-foil).
The seedlings are visibly leggy; the grow-light section below has a measured explanation.
The `TANK -0.0%` reading is solved: the photo was taken at 12:41, the tank sensor's last good
reading was 10:46 that morning, and the display was printing `-nan%`, which at 18 px reads as
`-0.0%`. See [Known issues](docs/known-issues.md).*

## At a glance

| | |
|---|---|
| Problem | Basil indoors with no natural light. A timer cannot see the soil. The pot is bottom-watered. |
| What I built | A closed-loop ebb-and-flow rig: one pump floods a tray with a measured dose, gravity drains it back to the tank, a capacitive soil probe decides when to water, an ultrasonic sensor guards the tank, and a NodeMCU v3 reports to Home Assistant. |
| Result | A 1.8cm setpoint delivers ~1.9cm (~247 ml) in ~34s. The four grow rings draw 6.2W total, ~10% of the 60W nameplate. After removing `captive_portal:` the device ran 12.8 hours continuously with Home Assistant as the only client. |
| Stack | ESP8266 (NodeMCU v3) with ESPHome, Home Assistant on a Raspberry Pi 4, one 12V supply and three DC-DC converters. |
| Status | Deployed and not finished — open items below. Last dated measurement in this README: 2026-09-21. |

## How it works

```
                    every 10 min: soil < "Water below"?
                    tank has a full dose above the floor?
                    no drain fault? lockout expired?
                              |
                              v
                    ,----------------------.
                    | FLOOD: pump on        |  poll every 2s, stop on:
                    | (max 120s)             |   - dose reached
                    `----------------------'    - tank floor reached (6cm)
                              |                  - no flow 20s -> re-prime,
                              v                    up to 3x, else abort
                    ,----------------------.
                    | DRAIN: pump off,      |  gravity siphon return,
                    | wait 3 min             |  ~80-90s on the real rig
                    `----------------------'
                              |
                              v
                    ,----------------------.
                    | SOAK: wait 10 min,    |  bottom watering wicks
                    | then read soil        |  upward slowly; reading
                    `----------------------'    immediately reports the
                              |                  transient, not the truth
                    soil >= "Stop at"? --- yes -> done
                              |
                              no, and cycles < "Max cycles" (5)
                              |
                              `---> loop again
```

- A pot of basil sits inside a tray; the tray sits above a reservoir tank.
- A single pump floods the tray with a measured dose, then is simply switched off — the tray
  drains back through the same tube by gravity siphon.
- The soil probe decides whether the plant needs water and whether a cycle actually worked.
  The ultrasonic sensor measures the reservoir, which doubles as dose control and a dry-run
  guard.
- Home Assistant is the only user interface; the deployed firmware has no local web UI.

## Hardware

| Part | Model | Notes |
|---|---|---|
| MCU | NodeMCU v3 (Lolin), ESP8266EX | Serial flashing over USB (CH340), OTA otherwise |
| Soil moisture | HW-390 capacitive probe v2.0 | Powered from **3V3**, not 5V — see [Wiring](docs/hardware.md#pinout) |
| Tank level | HC-SR04 ultrasonic | 5V supply, 1k/2k divider on ECHO, blind zone 2cm |
| Box climate | DHT11 | Ambient box air, not the reservoir headspace |
| Display | SSD1306 0.96" OLED, I2C 0x3C | Mounted portrait (rotated 90°) |
| Relays | SRD-05VDC-SL-C, 4-channel (2 used) | JD-VCC jumper cap removed, fed separately |
| Pump | Submersible, 2.5–6V, ~3W | M7 diode across it for flyback suppression |
| Converters | 2× LM2596S (adjustable) + RY8326 (fixed 5V/3A) | See [Power](docs/hardware.md#power) |
| Reservoir | ON Gold Standard 900g whey tub | Body HDPE #2, lid PP #05, ~130 cm² effective cross-section (measured) |
| Tray | PP #05 container | ~500 ml, ~200 ml usable with the pot inside |

Full connection-by-connection wiring, including the pre-power-on checklist, is in
[`docs/WIRING.txt`](docs/WIRING.txt) (bilingual, diagrams in monospace ASCII). Note:
`docs/WIRING.txt` quotes a geometric cross-section (~143 cm²) computed from the tub's rim
radius alone; the firmware uses the measured figure (~130 cm², i.e. 1cm of level change ≈
130 ml) instead, since the tub tapers toward the base and the measured value is the one that
actually matches how much the level moves per litre.

The pinout, the wiring facts that destroy hardware if you get them wrong, the power
measurements and the OLED behaviour: [docs/hardware.md](docs/hardware.md).

## The engineering story: why the device kept resetting

The interesting engineering here turned out not to be the watering logic. It was keeping the
device itself alive long enough to run it.

**Symptom.** The ESP8266 reset several times an hour in bursts, with 86–113 minutes of clean
uptime between bursts. API clients saw `SocketClosedAPIError`, `EncryptionHelloAPIError`,
`HandshakeAPIError`, `TimeoutAPIError`.

**Measurement.** Ping kept answering at 1–2 ms the whole time, even while every API handshake
failed, and the rails measured 5.23V at the 5V input, 3.29V on 3V3 and 4.42V at the LED rings
under load. A device that answers ping is not proven to be able to serve a connection, and the
power measurements did not support a brownout (a microsecond transient is not ruled out).

**Trigger.** A second API client attempting a Noise handshake while one was already attached
crashes the device. 23 hours and 878 log lines produced zero exception resets; connecting a
second client produced three `Exception` resets in three minutes.

**Fix.** Removing `captive_portal:` freed 2008 B of static RAM (48900 → 46892 B) and 40922 B
of flash. The device then ran 12.8 hours continuously with Home Assistant as the sole client.

**What stays open.** The trigger is established; the mechanism is not. A code fault in the
handshake path and an allocation failure are both still live, because `max_block` at the
moment of the crash is unknown.

The operational rule that follows: exactly one API client, ever — and stopping the other
client is not enough until the device's own keepalive expires. The hypothesis table, the heap
evidence and the recorder lesson: [docs/stability.md](docs/stability.md).

## Watering loop and safety interlocks

The loop is closed on soil moisture, not on volume delivered — a single flood moves the probe
by only about 5% of its range, and the ultrasonic sensor's ~0.3cm resolution against a
~1.7–2.0cm dose is roughly 20% measurement granularity. Flood a fixed dose, drain it, wait
10 minutes for it to wick upward, read the probe, and go again if it is still dry.

Six interlocks guard the pump: an absolute floor of 6cm, a 130-second watchdog, a drain-fault
latch, a tank-empty guard, a 5-cycle cap, and a structural fail-safe (reservoir below tray,
gravity drain, mandatory overflow port).

Dose figures, prime retry, the fungus-gnat setpoints and the perforated-foil barrier:
[docs/watering.md](docs/watering.md).

## Grow light

Current schedule: **07:30–00:30 light (17h), 00:30–07:30 dark (7h)**. The firmware carries no
light schedule; `automation.basil_grow_light_schedule` in Home Assistant owns it, after three
firmware designs each failed in a specific way.

Four rings measured 6.2W total (4.45V / 0.35A each) work out to roughly 187 µmol/m²/s — about
11.4 mol/m²/day at 17h, at or just under the low edge of basil's 12–16 DLI target, and that estimate is optimistic. Mounting
clearance matters more than anything else: rings need to sit about 10cm above the canopy, and
the leggy seedlings in the photo are what happens when that clearance is not kept.

The three designs and the light-budget math: [docs/grow-light.md](docs/grow-light.md).

## Home Assistant integration

The device exposes itself over the ESPHome native API
(`Noise_NNpsk0_25519_ChaChaPoly_SHA256` encryption, key in `secrets.yaml`) to a Raspberry Pi 4
running Home Assistant. No local web UI and no MQTT — HA is the only interface by design.

Nine `sensor` entities (soil moisture %, soil voltage, tank %, tank depth, tank distance, box
temperature, humidity, WiFi signal, uptime), three `binary_sensor` entities (needs water, tank
empty, drain fault), one `switch` (grow light; the fill pump is deliberately not exposed),
five `number` entities (dose, max cycles, stop at, water below, lockout) and four `button`
entities (water now, calibrate: start fill, calibrate: save dose, clear drain fault). Three
alert automations notify on state change: drain fault, tank empty with a 5-minute debounce,
and device offline after 30 minutes.

Entity table and alert detail: [docs/home-assistant.md](docs/home-assistant.md). The 128×64
OLED, its three screens and the refresh-rate change: [docs/hardware.md](docs/hardware.md#oled).

## Limits and open items

Settled: the trigger for the resets. Open:

- The mechanism behind the reset — code fault or allocation failure — because `max_block` at
  the fault is unknown.
- `pump_min_cm` (currently 6, a guess) is not yet measured.
- The overflow port from tray to tank is not yet built.
- Whether the gnat-control dry-down changes the next cycle is not measured.
- The dawn half-cycle of the current light schedule has not been observed in production.
- The NaN display guards are in the config and validate, but are not yet flashed.

Full write-ups, including the three-hour outage that was a loose connector and the `-nan%`
explanation: [docs/known-issues.md](docs/known-issues.md).

## Build / run

```sh
cp secrets.yaml.example secrets.yaml
# edit secrets.yaml: at minimum set wifi_ssid / wifi_password.
# The other three keys are usable as-is, or regenerate your own -
# the OTA password is intentionally unset in this config (see comment
# in basil.yaml), and the API key is a base64 Noise PSK ESPHome can
# generate for you.

esphome run basil.yaml --device COM15      # first flash, over USB
esphome run basil.yaml --device basil.local  # subsequent updates, over OTA
```

Always pass `--device` explicitly — a bare `esphome run` prompts for a host interactively and
dies on EOF when run non-interactively.

There is no OTA password on this device by design: losing access to the source tree (and thus
the password) is judged more likely than someone else on the LAN pushing firmware. Recovery
without a password means opening the box and flashing over USB.

OTA also has to respect the one-API-client rule. Block Home Assistant, wait ~80s for its side
of the socket to clear, then wait a further ~2 minutes for the device's keepalive to expire
before uploading; done in that order, a real upload completed in **18.34 seconds, clean, first
try**. Treat 2 minutes as the shortest wait that has worked, not a guaranteed threshold. The
exact procedure and the two failed attempts: [docs/ota.md](docs/ota.md).

`basil-bench.yaml` is a separate, superseded build kept for reference: sensors and a local web
UI, no relays, no pump, no WiFi — used to read off calibration numbers on the bench before the
real rig existed. It's wired differently (see the comment block at the top of the file) and
should not be flashed onto the deployed device.

## Repo layout

```
basil.yaml              the deployed firmware (ESPHome)
basil-bench.yaml         superseded bench build - sensors only, local web UI
secrets.yaml.example     template for secrets.yaml (gitignored)
docs/WIRING.txt          full wiring diagram + pre-power-on checklist
docs/img/                photos referenced from this README
serial-monitor.ps1       raw serial monitor for USB-flash debugging
set-numbers.py           set a `number` entity over the API (bypasses HA)
trigger-water.py         press "Water now" and stream the device log
watch-water.py           same, but reconnects through drops - used to
                         capture a full watering cycle across API resets
```

All three Python scripts open their own API connection to the device. Per
[the stability story](#the-engineering-story-why-the-device-kept-resetting), that makes them
a second client whenever Home Assistant is already attached — which crashes the device, not
just the script. Free the slot first (stop or block HA's connection) and wait for the device's
own keepalive to expire, not just for HA's socket to close, before running any of them.

## License

MIT — see [LICENSE](LICENSE).
