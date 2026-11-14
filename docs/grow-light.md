# Grow light, and why the schedule lives in Home Assistant, not firmware

The firmware went through three designs before landing here, and each failure is informative:

1. **Time-triggered edges in firmware** (on at a fixed hour, off at another), with the relay's
   restore mode set to `RESTORE_DEFAULT_OFF`. A daytime reboot or OTA restored the relay to
   *off* and left the plants dark until the next scheduled "on" edge.
2. **60-second re-assertion loop in firmware.** Fixed the reboot problem by re-applying the
   scheduled state every minute — which also meant a manual toggle at bedtime got silently
   undone within 60 seconds. Correct for autonomy, wrong for actually living with the thing.
3. **Home Assistant owns the schedule.** The firmware carries no light schedule at all now —
   the relay is just a `switch` entity. Home Assistant's
   `automation.basil_grow_light_schedule` fires on two time triggers plus a
   `homeassistant: start` recovery trigger (an earlier "device came back online" trigger was
   removed — it turned out `esp8266: restore_from_flash: true` already preserves relay state
   across reboots, so that trigger was firing on ordinary 3-second API blips and issuing
   unwanted switch commands). A manual override now sticks until the next scheduled boundary,
   because nothing re-asserts in between.

Current schedule: **07:30–00:30 light (17h), 00:30–07:30 dark (7h)** — shifted from an
original 18h design to fit the room it's in. The 18h design target is worth keeping for the
light-budget math: four rings measured at their brightest controller setting (4.45V / 0.35A
each = 1.56W/ring, 6.2W total — about 10% of the 60W nameplate) work out to roughly
187 µmol/m²/s and a Daily Light Integral around 12.1 mol/m²/day at 18h — scaled to the current
17h schedule, roughly 11.4 mol/m²/day — which sits at or just under the *low* edge of basil's
usual 12–16 DLI target, and that estimate is optimistic since it assumes every photon lands on
the pot. **Mounting clearance matters more than anything else here**: PPFD falls off as
1/distance², so rings need to sit close to the canopy — about 10cm above it — and the photos
in the [README](../README.md) show what happens when that clearance isn't kept: long pale
internodes reaching for the light instead of compact growth.
