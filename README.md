# Basil grow-box: closed-loop ebb-and-flow irrigation on an ESP8266

**English** · [繁體中文](README.zh-TW.md)

![The grow-box: a terracotta pot of basil seedlings sitting in the mouth of a translucent plastic bucket reservoir, rim sealed with foil and tape, under four ring-light lamps on gooseneck stalks clamped to a shelf edge. To the left, a NodeMCU ESP8266 on perfboard with an SSD1306 OLED and a blue 4-channel relay module. Below the shelf, a black tub holding a second board on its lid. The OLED reads 12:41, SOIL 100%, TANK -0.0%, 28.0 C 65% RH.](docs/img/rig-hero.jpg)

*The rig as built. Seedlings are visibly leggy — long pale stems, sparse leaves — a symptom the [grow-light section](#grow-light-and-why-the-schedule-lives-in-home-assistant-not-firmware) below has a measured explanation for. The `TANK -0.0%` reading is real and unexplained; see the [known issues](#known-issues--open) section.*

Indoor basil, zero natural light, bottom-watered by ebb and flow: a pump floods
the outer tray, the water drains back to the reservoir by gravity, and an
ESP8266 decides when to run the cycle by reading the soil directly rather than
on a timer. Grow lights are on a schedule too, but that schedule deliberately
does **not** live in the firmware — see below for why.

The interesting engineering here turned out not to be the watering logic. It
was keeping the device itself alive long enough to run it — see
[The stability story](#the-stability-story-why-the-device-kept-resetting).

## What it is

- A pot of basil sits inside a tray; the tray sits above a reservoir tank.
- A single pump floods the tray with a measured dose of water, then is simply
  switched off — the tray drains back to the tank by gravity siphon through
  the same tube it was filled through.
- A capacitive soil probe decides whether the plant needs water and whether a
  flood/drain cycle actually worked. An ultrasonic sensor on the tank measures
  how much water is in the reservoir, which doubles as dose control and a
  dry-run guard.
- A NodeMCU v3 (ESP8266) runs the whole loop and reports to Home Assistant
  over the ESPHome native API. Home Assistant is the only user interface —
  there is no local web UI on the deployed firmware.

## Hardware

| Part | Model | Notes |
|---|---|---|
| MCU | NodeMCU v3 (Lolin), ESP8266EX | Serial flashing over USB (CH340), OTA otherwise |
| Soil moisture | HW-390 capacitive probe v2.0 | Powered from **3V3**, not 5V — see [Wiring](#wiring--pinout) |
| Tank level | HC-SR04 ultrasonic | 5V supply, 1k/2k divider on ECHO, blind zone 2cm |
| Box climate | DHT11 | Ambient box air, not the reservoir headspace |
| Display | SSD1306 0.96" OLED, I2C 0x3C | Mounted portrait (rotated 90°) |
| Relays | SRD-05VDC-SL-C, 4-channel (2 used) | JD-VCC jumper cap removed, fed separately |
| Pump | Submersible, 2.5–6V, ~3W | M7 diode across it for flyback suppression |
| Converters | 2× LM2596S (adjustable) + RY8326 (fixed 5V/3A) | See [Power](#power) |
| Reservoir | ON Gold Standard 900g whey tub | Body HDPE #2, lid PP #05, ~130 cm² effective cross-section (measured) |
| Tray | PP #05 container | ~500 ml, ~200 ml usable with the pot inside |

Full connection-by-connection wiring, including the pre-power-on checklist, is
in [`docs/WIRING.txt`](docs/WIRING.txt) (bilingual, diagrams in monospace ASCII).
Note: `docs/WIRING.txt` quotes a geometric cross-section (~143 cm²) computed
from the tub's rim radius alone; the firmware uses the measured figure
(~130 cm²/cm) instead, since the tub tapers toward the base and the measured
value is the one that actually matches how much the level moves per litre.

## Wiring / pinout

Every GPIO choice here is constrained by the ESP8266's boot-strapping pins —
several GPIOs carry a required level at reset, and getting one wrong either
prevents boot or prevents flashing.

```
  A0  soil (HW-390 AOUT, 3V3 supply)
  D1  GPIO5   OLED SCL
  D2  GPIO4   OLED SDA                    (I2C 0x3C)
  D3  GPIO0   relay IN1 -> grow light     (pulled high at boot: boot-mode select)
  D4  GPIO2   HC-SR04 TRIG                (strapping pin — must unplug the
                                            sensor to enter USB flash mode)
  D5  GPIO14  HC-SR04 ECHO, through 1k/2k divider
  D6  GPIO12  relay IN2 -> fill pump
  D7  GPIO13  DHT11 data, 10k pullup to 3V3
  D0  GPIO16  free (candidate: move TRIG here — not a strapping pin)
  D8  GPIO15  UNUSED — pulled low at boot; an active-low peripheral would
              latch the board on
```

Two wiring facts worth calling out because getting them wrong destroys
hardware rather than just misbehaving:

- **HC-SR04 ECHO must be divided.** The ESP8266EX's absolute maximum GPIO
  input is 3.6V; a 5V-powered HC-SR04 puts 5V logic straight onto ECHO without
  one. This is the only place in the whole build where skipping a part
  permanently burns something out. Only two ECHO wirings are safe: 5V supply
  *with* the divider, or 3V3 supply *without* it — and a bare 5V-without-divider
  wiring will read perfectly fine while slowly damaging the pin, so a working
  reading is not proof the wiring is correct.
- **Relay logic VCC must be 3V3, not 5V.** These boards are opto-isolated;
  with a 3.3V GPIO driving IN, a 5V logic rail still leaves ~0.5 mA flowing
  through the opto on "high" and the relay never releases. At 3V3 it's 2.1 mA
  on / 0 mA off — a clean switch.
- **`JD-VCC` (the coil rail) must come from an always-on supply.** If it were
  fed from a rail that a relay itself switches, opening that relay would cut
  its own coil power and it could never re-close.

## Power

Three DC-DC converters run off a single 12V supply, all **permanently
energized** — the relays switch the converter *outputs*, not the 12V inputs.
That trades a small idle draw (~0.1–0.3W per converter) for two things: the
LEDs never see a converter's cold-start voltage overshoot, and each rail can
be trimmed and verified under its actual working load rather than guessed at.

| Converter | Output | Feeds | Measured |
|---|---|---|---|
| LM2596S #1 | 4.45V (set under load) | 4× LED grow rings via relay CH1 | 1.4A / 6.2W total (4 rings), ~10% of the 60W nameplate |
| LM2596S #2 | 5.00V | Submersible pump via relay CH2 | 0.6A run, ~2A stall pulse (tens of ms) |
| RY8326 | Fixed 5.0V / 3A | NodeMCU VIN, DHT11, HC-SR04, relay JD-VCC | ~0.5A, runs cool |

A pump motor's back-EMF is real: an M7 diode (1A/1000V) sits across the pump
leads, band toward +. Because the relay switches the converter *output* here,
the contact is directly interrupting the motor current — without the diode,
the flyback pulse arcs across the relay contact and pits it a little on every
cycle.

## Watering loop

The loop is **closed on soil moisture, not on volume delivered.** A single
flood only moves the soil probe's reading by about 5% of its range, and the
ultrasonic sensor's ~0.3cm resolution against a ~1.7–2.0cm dose is roughly 20%
measurement granularity — metering an exact water volume was never going to be
precise enough to be the control variable. So instead: flood a fixed dose,
drain it, wait for it to wick upward, read the probe, and go again if it's
still dry.

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

- **Dose** delivered in practice: a 1.8cm setpoint delivers ~1.9cm (~247 ml)
  in ~34s — about 6s to clear air from the siphon tube plus ~28s of actual
  flow. The 2-second poll interval against an ~0.06–0.07 cm/s fill rate means
  the loop structurally overshoots its own setpoint by ~0.1–0.2cm; setpoint
  changes smaller than ~0.3cm are inside that noise.
- **Prime retry.** The siphon empties the delivery tube on every drain, so
  every flood has to push roughly a 70cm column of air out of the line first.
  A small centrifugal pump can't self-prime against that reliably. If the tank
  level hasn't moved in 20 seconds, the pump is cut for 3 seconds — letting
  water fall back and re-flood the impeller housing — then restarted. Up to
  three tries before the cycle aborts as a dry run.
- **Fungus gnat control via the moisture setpoints.** `Stop at` moved 70% →
  55% and `Water below` moved 30% → 22% (2026-09-20): the soil probe sits near
  the surface, so these numbers are effectively an instruction for how wet to
  keep the top few centimetres — which is the entire habitat of *Sciaridae*
  larvae. The root zone stays saturated from bottom watering either way; only
  the surface is deliberately kept drier, and a dry spell of 4–5 days breaks a
  3–4 day gnat generation cycle instead of just slowing it down.

## Safety interlocks

None of these are optional; each one guards a specific failure mode observed
or reasoned through during the build.

- **Absolute pump floor (`pump_min_cm`, 6cm).** Checked every 2 seconds inside
  the flood loop regardless of dose progress. A submersible pump is cooled by
  the water it moves — running dry kills it in seconds, faster than the 20s
  no-flow detector could catch it. *(This value is still an estimated
  placeholder — see [Known issues](#known-issues--open).)*
- **Independent pump watchdog.** A hard 130-second cutoff for the fill pump,
  built as a cancellable `script` rather than an inline `delay:` — ESPHome
  can't cancel an inline delay, so an earlier version fired 130s after the
  *first* pump start regardless of prime retries turning it off and back on
  in between, which could have cut a legitimately re-primed fill short.
- **Drain fault latch — and its actual reset behaviour, which is subtler than
  it first looks.** If more than 40% of a dose's worth of water hasn't
  returned to the tank by the end of the drain wait, `drain_fault` latches
  `on` and takes over the OLED. The automatic 10-minute trigger checks the
  latch and refuses to start a new cycle while it's set — but the manual
  `button.basil_water_now` ("Water now") does **not** check it, and will run
  a cycle regardless. That matters because `drain_fault` is recomputed at the
  end of *every* `water_cycle` run, whichever trigger started it: if that run
  completes with water actually returning, the flag clears itself; if the run
  aborts as a dry run (or never had enough water above the floor to attempt a
  cycle at all), the flag is left exactly as it was. `button.basil_clear_drain_fault`
  is the only path that clears it without running water at all.
- **Tank-empty guard.** `tank_cm < pump_min_cm` triggers `binary_sensor.basil_tank_empty`
  before any cycle is allowed to run; the Home Assistant alert debounces this
  5 minutes to ride out the ordinary transient dip during an active flood.
- **Max cycles cap (5).** A capacitive probe with poor soil contact reads
  falsely dry (a real failure seen during planting: after thinning, an
  air-gapped probe read 50–51% in saturated soil until the soil was firmed
  back around it). Without a hard cap, a lying probe would flood the tray
  indefinitely.
- **Structural, not software, fail-safe on drainage.** The reservoir sits
  *below* the tray. Pump off — for any reason, including a power cut — means
  gravity drains the tray back down on its own; there is no drain pump or
  H-bridge to fail in the wrong direction. A welded relay contact is the one
  failure this can't protect against on its own, which is why the tray also
  has a **mandatory overflow port** back to the tank, sized for the ~10:1
  volume ratio between the two vessels (~2.3 L tank vs ~200 ml usable tray).

## Grow light, and why the schedule lives in Home Assistant, not firmware

The firmware went through three designs before landing here, and each failure
is informative:

1. **Time-triggered edges in firmware** (on at a fixed hour, off at another),
   with the relay's restore mode set to `RESTORE_DEFAULT_OFF`. A daytime
   reboot or OTA restored the relay to *off* and left the plants dark until
   the next scheduled "on" edge.
2. **60-second re-assertion loop in firmware.** Fixed the reboot problem by
   re-applying the scheduled state every minute — which also meant a manual
   toggle at bedtime got silently undone within 60 seconds. Correct for
   autonomy, wrong for actually living with the thing.
3. **Home Assistant owns the schedule.** The firmware carries no light
   schedule at all now — the relay is just a `switch` entity. Home Assistant's
   `automation.basil_grow_light_schedule` fires on two time triggers plus a
   `homeassistant: start` recovery trigger (an earlier "device came back
   online" trigger was removed — it turned out `esp8266: restore_from_flash:
   true` already preserves relay state across reboots, so that trigger was
   firing on ordinary 3-second API blips and issuing unwanted switch
   commands). A manual override now sticks until the next scheduled boundary,
   because nothing re-asserts in between.

Current schedule: **07:30–00:30 light (17h), 00:30–07:30 dark (7h)** —
shifted from an original 18h design to fit the room it's in. The 18h design
target is worth keeping for the light-budget math: four rings measured at
their brightest controller setting (4.45V / 0.35A each = 1.56W/ring, 6.2W
total — about 10% of the 60W nameplate) work out to roughly 187 µmol/m²/s and
a Daily Light Integral around 12.1 mol/m²/day at 18h — scaled to the current
17h schedule, roughly 11.4 mol/m²/day — which sits at or just under the *low*
edge of basil's usual 12–16 DLI target, and that estimate is optimistic since
it assumes every photon lands on the pot. **Mounting clearance matters more
than anything else here**: PPFD falls off as 1/distance², so rings need to sit
close to the canopy — about 10cm above it — and the photos in this README show
what happens when that clearance isn't kept: long pale internodes reaching for
the light instead of compact growth.

## Home Assistant integration

The device exposes itself over the ESPHome native API
(`Noise_NNpsk0_25519_ChaChaPoly_SHA256` encryption, key in `secrets.yaml`) to
a Raspberry Pi 4 running Home Assistant. It does not run a local web UI or
MQTT — HA is the only interface by design (see the note in `basil.yaml` on why
`web_server:` was removed: an ESP8266 serves very few simultaneous
connections, and a browser holding a web UI's SSE stream competes directly
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
- **Tank empty** — 5-minute debounce to ride out the transient dip during an
  active flood.
- **Device offline** — `sensor.basil_uptime` going `unavailable` for 30
  minutes, long enough to ride out an HA restart or a normal Wi-Fi blip
  without paging anyone for nothing.

## OLED

128×64 SSD1306, physically mounted on its side and driven as a 64-wide,
128-tall portrait canvas. Three screens: idle, running (shows phase — `FILL`,
`DRAIN`, `SOAK`, `PRIME` — and cycle count), and drain fault (full-screen,
takes over regardless of light state). The display goes dark whenever the
grow light is off, with two deliberate exceptions: a latched fault or an
in-progress cycle always stay lit, because a blank screen must never hide
something that needs a human.

The refresh rate is 500ms, and it used to be 250ms driving a full-screen
inversion twice a second as an "attention" cue. That inversion was removed:
an all-pixels-lit SSD1306 draws 25–30 mA against ~6 mA for ordinary text, and
toggling that load at 2 Hz tugged the 3.3V rail hard enough to show up as ADC
noise and ultrasonic jitter — a plausible contributor to an API drop observed
mid-flood. The attention cue is now a static 2px border plus one small
inverted badge, at a fraction of the current swing.

## The stability story: why the device kept resetting

This is the most interesting part of the build, and it's worth being precise
about what was actually established versus what was ruled out.

**Symptom.** The ESP8266 reset several times an hour in bursts, with 86–113
minutes of clean uptime between bursts. From an API client the failures
looked like `SocketClosedAPIError`, `EncryptionHelloAPIError`,
`HandshakeAPIError`, `TimeoutAPIError`.

**The discriminator that mattered:** ping kept answering at 1–2 ms the entire
time, even while every API handshake failed. ICMP on this device is served by
the SDK/lwIP network stack, not by the Arduino main loop — so a device that
answers ping is not proven to be able to serve a connection at all. That one
fact is what kept the debugging honest instead of chasing "the device is
online, so it can't be a firmware fault."

Three plausible causes were raised and killed, each by a specific measurement:

| Hypothesis | Why it looked plausible | What killed it |
|---|---|---|
| HA holds the only API slot, and that's inherently unstable | Home Assistant was connected during every failure | Two clean runs, 86.7 min and 112.7 min, with HA connected and **idle** the whole time |
| Connection churn (reconnects, log streaming) crashes it | Every reset cluster coincided with *someone doing something* | That's confounded, not causal — flashing, watering tests and DEBUG log streaming all happened during the same windows |
| Power sag under load (pump/LED in-rush) | Textbook brownout shape | Measured 5.23V at the 5V input, **3.29V on 3V3**, 4.42V at the LED rings under load — a chronic droop would read under 3.0V. (A microsecond transient during WiFi TX is *not* ruled out — a multimeter can't see one — but 3.29V standing leaves little room for it to matter.) |

A planned bulk-capacitor mod (470µF + 0.1µF across 3V3) was designed and then
**stood down** once these measurements came in — its whole premise was a
voltage problem the data didn't support.

**Heap was suspected first, and the evidence turned out to say the opposite.**
The three heap samples immediately before one crash were the *healthiest of
the night*: `free=6816 B, max_block=11600 B, frag=4%`. Almost 7 kB free with
an 11.6 kB contiguous block is not what an allocation failure looks like —
this reading directly contradicted the heap-starvation theory and retracted
it.

**Actual cause, confirmed by direct causal evidence:** a *second* API client
attempting a Noise handshake while one was already attached crashes the
device outright. `reset_reason` reads `Exception` — an ESP8266 firmware
fault, not a watchdog bite and not a brownout. The clearest data point: 23
hours and 878 log lines with zero exception resets, then a second client was
deliberately connected — 3 exception resets followed in 3 minutes, each one
20–60 seconds after a failed handshake attempt. Stopping the second client
stopped the resets.

**The operational rule that follows:** exactly one API client, ever. Home
Assistant holds it. And there's a subtlety that costs real debugging time if
you miss it — **stopping the other client isn't enough on its own.** The
device keeps its half of a dropped connection alive until its own keepalive
expires; connecting inside that window still counts as a second client and
still crashes it, confirmed by a reset that happened when a script connected
three minutes after the other side's socket had already closed.

**The fix that shipped:** removing `captive_portal:`, which pulls in a web
server and DNS server neither used in practice, freed 2008 B of static RAM
(48900 → 46892 B) and 40922 B of flash. The device then ran **12.8 hours
continuously** with HA as the sole client — the control run that everything
else is measured against.

**One number worth carrying forward on its own:** adding the diagnostics that
found all of this — heap sensors, reset-reason reporting — cost about 655 B,
roughly 0.8% of total RAM. On a device with 3–4 kB free, that's a fifth of the
remaining headroom. Measuring the edge moved the edge.

## Known issues / open

This device is not "done." What's genuinely settled and what isn't:

- **Settled:** the root cause of the reset bursts (a second API client
  crashing the ESP8266's Noise handshake), and the operational + code
  mitigations above.
- **Open:** *why* ESPHome 2025.7.5's API component on ESP8266 faults on a
  second handshake attempt instead of just refusing it. Worth checking
  against a newer ESPHome release before assuming it's unfixable in this
  version.
- **Open:** no *spontaneous* `reset_reason` has been captured yet — every
  reset logged so far followed a flash, an OTA, or a deliberate second
  client. The next unplanned reset is the evidence that would either confirm
  the cause is fully closed or reopen it.
- **Open:** whether the post-fix `max_block` (3176 B) is comfortably above
  whatever threshold the Noise handshake actually needs, or just happens to
  be above it. This isn't practically testable without deliberately crashing
  the device again.
- **Not yet measured:** `pump_min_cm` (currently 6, a guess) — the intended
  process is to stand the pump on the tank floor, add water until it primes
  without gurgling, and set the floor 1cm above that depth.
- **Not yet built:** the overflow port from tray to tank. Structurally this is
  the only thing that protects against a welded relay contact, given the tray
  holds roughly a tenth of what the tank does — and it matters even in normal
  operation, not just fault cases: the tray's own usable headroom around the
  pot (~200 ml) is already close to the ~247 ml a normal dose delivers.
  Until the port exists, the two calibration buttons below are the sharper
  version of the same risk: they have no dose-based cutoff of their own, only
  the 130-second pump watchdog, so an unattended calibration run can push
  close to a litre through the tray.
- **Unexplained:** the `TANK -0.0%` reading visible on the OLED in the hero
  photo above. The tank-percentage sensor is clamped to a 0–100 range in the
  firmware, so a negative display value on real hardware doesn't yet have a
  traced cause — it's left here rather than guessed at.
- **Not yet observed in production:** a full "dawn" half-cycle of the current
  Home Assistant light schedule (dusk was verified; dawn had not fired yet as
  of the last recorded check).

## Build / flash / OTA

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

Always pass `--device` explicitly — a bare `esphome run` prompts for a host
interactively and dies on EOF when run non-interactively.

There is no OTA password on this device by design: the tradeoff made here is
that losing access to the source tree (and thus the password) is judged more
likely than someone else on the LAN pushing firmware. Recovery without a
password means opening the box and flashing over USB.

`basil-bench.yaml` is a separate, superseded build kept for reference: sensors
and a local web UI, no relays, no pump, no WiFi — used to read off calibration
numbers on the bench before the real rig existed. It's wired differently (see
the comment block at the top of the file) and should not be flashed onto the
deployed device.

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
[the stability story](#the-stability-story-why-the-device-kept-resetting),
that makes them a second client whenever Home Assistant is already attached
— which crashes the device, not just the script. Free the slot first (stop
or block HA's connection) and wait for the device's own keepalive to expire,
not just for HA's socket to close, before running any of them.

## License

MIT — see [LICENSE](LICENSE).
