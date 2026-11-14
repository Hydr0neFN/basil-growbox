# Known issues / open

## A three-hour outage that was a loose connector — and what it accidentally measured

On 2026-09-20 the HC-SR04 stopped reading and the board would not boot with it connected. It
was a **loose DuPont connector**, reseated at 13:46, and the sensor came back immediately. The
write-up survives because two things it produced are worth more than the fault was.

**Firmware was excluded by timeline, not by argument.** The first instinct was that recent
firmware changes had broken it. The build flashed at 00:58 read a steady **7.82-7.85 cm
continuously until 10:24** — 9.5 hours. It went unavailable during a session of physical work,
gave one last good reading at **10:46:02**, and produced nothing after, while the device itself
stayed up. Same binary either side of a hardware intervention, so the revisions could not be
the cause. A recorder on the Pi settled in one query what would otherwise have been an
afternoon of bisecting firmware.

**The proof it was only ever the connection is unusually clean:**

```
10:46:02  last good      7.82039976119995 cm   95.1166687011719 %
13:46:47  after reseat   7.82039976119995 cm   95.1166687011719 %
```

Bit-for-bit identical, three hours apart. The water level had not moved and the sensor had not
drifted.

**And that identity measured something that had only been reasoned.** The section below argues
that with the tank sensor reading NaN, every pump gate compares false and no watering can run.
That was inference. Three hours of an unchanged water level, to the last digit, is evidence:
no cycle ran in that window. Inference at 13:00, measurement at 13:46.

A working hypothesis was recorded during the outage — that the module had failed in a way that
loaded TRIG, which would have explained the read failure and the boot failure with one fault.
**It is retracted.** It was parsimonious and wrong; the connector was on the same suspect list
and was the cheapest item on it. Note what that means for the boot symptom: it is **not**
explained by a loaded TRIG, and remains the original GPIO2 strapping hazard. A loose connector
plausibly makes that hazard surface more readily, but that is not established and should not
be written as though it were.

Two other suspects were ruled out along the way. The ECHO 1k/2k divider is **SMD 0805,
soldered**, not flying leads, so a pulled divider wire was never in play. And the aluminium
foil did **not** touch anything near the HC-SR04.

## The display was printing `-nan%`, and three guards let it through

The `TANK -0.0%` on the hero photo in the [README](../README.md) was never a rendering bug or
a stale value. `sensor.basil_tank` has been `unknown` since 10:47:20, Home Assistant renders a
NaN state as `unknown`, and the OLED was printing `-nan%` — which in the 18 px font is a
convincing `-0.0%`.

NaN walked through three guards in a row, and each one failed for a different reason:

| Guard | Why it did not catch NaN |
|---|---|
| `has_state()` | A NaN state *is* a published state. Passes. |
| `clamp {min: 0, max: 100}` | Every comparison against NaN is false, so neither bound bites. Passes. |
| `printf("%.0f")` | Renders it as `-nan`. |

The clamp genuinely is there and genuinely does nothing. Display guards are now
`has_state() && !std::isnan(state)`, and the TANK block gained a `--` else-branch it never had
— previously a dead tank drew nothing at all, which reads as a broken screen rather than a
broken sensor. Config validates; not yet flashed.

## With the tank sensor dead the rig was safe by accident, not by design

Worth stating plainly, because it is exactly the kind of thing a later, well-meaning "fix NaN
handling" could turn into a fail-open.

Every pump gate is a comparison against `tank_cm` — the pre-cycle check
(`(tank_cm - dose_cm) > pump_min_cm`) and the in-loop floor (`tank_cm > pump_min_cm`). **Every
comparison against NaN is false**, so neither gate could pass: no cycle could start, and a
running one could not continue. With the sensor dead the pump simply could not run — and the
bit-identical water level three hours later confirms none did.

The same semantics silently disable the tank-empty alert, which is the mirror image of the
same fact: during the outage there was no level protection at all, only inaction. Safe, but
for a reason nobody designed.

**One more consequence, on a different sensor.** The foil did touch the **capacitive soil
probe**. That damages nothing, but a conductive sheet against a capacitive sensor couples into
the sense electrodes and inflates the reading toward wet. Any soil percentage taken in that
state is unusable. Note what this does and does not invalidate: it invalidates the
*measurement condition*, not the calibration figures recorded above.

Whenever the wiring is next opened, the YAML already documents a clean improvement worth
taking: **move TRIG from D4/GPIO2 to D0/GPIO16**, so serial flashing stops requiring the
sensor to be unplugged. The strapping hazard is an accepted design compromise. It is *not* the
thing that caused this outage, and this entry is careful not to imply the fault proved it
necessary.

This device is not "done." What's genuinely settled and what isn't:

- **Settled — the trigger:** a second API client attempting a Noise handshake while one is
  attached crashes the device. Zero Exception resets in 23 hours, three in three minutes the
  moment a second client was armed, and none after it stopped. That is empirical and holds
  whatever the mechanism turns out to be. The operational and code mitigations above follow
  from it.
- **Open — the mechanism.** A code fault in the handshake path and an allocation failure are
  both still live, because `max_block` at the moment of the fault is unknown (see
  [the stability story](stability.md) for why the logged value cannot be trusted as a
  snapshot). Separating them needs `max_block` sampled at the fault, which the current watcher
  cannot do without per-field timestamps.
- **Open:** *why* ESPHome 2025.7.5's API component on ESP8266 faults on a second handshake
  attempt instead of just refusing it. Worth checking against a newer ESPHome release before
  assuming it's unfixable in this version.
- **Open:** no *spontaneous* `reset_reason` has been captured yet — every reset logged so far
  followed a flash, an OTA, or a deliberate second client. The next unplanned reset is the
  evidence that would either confirm the cause is fully closed or reopen it.
- **Open:** whether the post-fix `max_block` (3176 B) is comfortably above whatever threshold
  the Noise handshake actually needs, or just happens to be above it. This isn't practically
  testable without deliberately crashing the device again.
- **Not yet measured:** `pump_min_cm` (currently 6, a guess) — the intended process is to
  stand the pump on the tank floor, add water until it primes without gurgling, and set the
  floor 1cm above that depth.
- **Not yet built:** the overflow port from tray to tank. Structurally this is the only thing
  that protects against a welded relay contact, given the tray holds roughly a tenth of what
  the tank does — and it matters even in normal operation, not just fault cases: the tray's
  own usable headroom around the pot (~200 ml) is already close to the ~247 ml a normal dose
  delivers. Until the port exists, the two calibration buttons below are the sharper version
  of the same risk: they have no dose-based cutoff of their own, only the 130-second pump
  watchdog, so an unattended calibration run can push close to a litre through the tray.
- **Unexplained:** the `TANK -0.0%` reading visible on the OLED in the hero photo in the
  [README](../README.md). The tank-percentage sensor is clamped to a 0–100 range in the
  firmware, so a negative display value on real hardware doesn't yet have a traced cause —
  it's left here rather than guessed at.
- **Not yet observed in production:** a full "dawn" half-cycle of the current Home Assistant
  light schedule (dusk was verified; dawn had not fired yet as of the last recorded check).
- **Not yet checked:** whether the gnat-control dry-down (soil pulled down to 22% between
  waterings) changes how the *following* cycle behaves. A more parched pot plausibly absorbs
  more water on rewetting than the ~247 ml baseline this document's dose figures are built on,
  which is exactly the kind of shift that could nudge the drain-fault math. No measurement
  exists yet either way.
