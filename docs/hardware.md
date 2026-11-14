# Hardware: pinout, wiring hazards, power and the OLED

The part table and the reservoir cross-section note stay in the [README](../README.md#hardware).
This file holds the pinout, the wiring facts that destroy hardware when they are wrong, the
power measurements and the display behaviour.

## Pinout

Every GPIO choice here is constrained by the ESP8266's boot-strapping pins — several GPIOs
carry a required level at reset, and getting one wrong either prevents boot or prevents
flashing.

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

These wiring facts are worth calling out, because getting them wrong destroys hardware rather
than just misbehaving:

- **HC-SR04 ECHO must be divided.** The ESP8266EX's absolute maximum GPIO input is 3.6V; a
  5V-powered HC-SR04 puts 5V logic straight onto ECHO without one. This is the only place in
  the whole build where skipping a part permanently burns something out. Only two ECHO wirings
  are safe: 5V supply *with* the divider, or 3V3 supply *without* it — and a bare
  5V-without-divider wiring will read perfectly fine while slowly damaging the pin, so a
  working reading is not proof the wiring is correct.
- **Relay logic VCC must be 3V3, not 5V.** These boards are opto-isolated; with a 3.3V GPIO
  driving IN, a 5V logic rail still leaves ~0.5 mA flowing through the opto on "high" and the
  relay never releases. At 3V3 it's 2.1 mA on / 0 mA off — a clean switch.
- **`JD-VCC` (the coil rail) must come from an always-on supply.** If it were fed from a rail
  that a relay itself switches, opening that relay would cut its own coil power and it could
  never re-close.

## Power

Three DC-DC converters run off a single 12V supply, all **permanently energized** — the relays
switch the converter *outputs*, not the 12V inputs. That trades a small idle draw (~0.1–0.3W
per converter) for two things: the LEDs never see a converter's cold-start voltage overshoot,
and each rail can be trimmed and verified under its actual working load rather than guessed at.

| Converter | Output | Feeds | Measured |
|---|---|---|---|
| LM2596S #1 | 4.45V (set under load) | 4× LED grow rings via relay CH1 | 1.4A / 6.2W total (4 rings), ~10% of the 60W nameplate |
| LM2596S #2 | 5.00V | Submersible pump via relay CH2 | 0.6A run, ~2A stall pulse (tens of ms) |
| RY8326 | Fixed 5.0V / 3A | NodeMCU VIN, DHT11, HC-SR04, relay JD-VCC | ~0.5A, runs cool |

A pump motor's back-EMF is real: an M7 diode (1A/1000V) sits across the pump leads, band
toward +. Because the relay switches the converter *output* here, the contact is directly
interrupting the motor current — without the diode, the flyback pulse arcs across the relay
contact and pits it a little on every cycle.

## OLED

128×64 SSD1306, physically mounted on its side and driven as a 64-wide, 128-tall portrait
canvas. Three screens: idle, running (shows phase — `FILL`, `DRAIN`, `SOAK`, `PRIME` — and
cycle count), and drain fault (full-screen, takes over regardless of light state). The display
goes dark whenever the grow light is off, with two deliberate exceptions: a latched fault or
an in-progress cycle always stay lit, because a blank screen must never hide something that
needs a human.

The refresh rate is 500ms, and it used to be 250ms driving a full-screen inversion twice a
second as an "attention" cue. That inversion was removed: an all-pixels-lit SSD1306 draws
25–30 mA against ~6 mA for ordinary text, and toggling that load at 2 Hz tugged the 3.3V rail
hard enough to show up as ADC noise and ultrasonic jitter — a plausible contributor to an API
drop observed mid-flood. The attention cue is now a static 2px border plus one small inverted
badge, at a fraction of the current swing.
