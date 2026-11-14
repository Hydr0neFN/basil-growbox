# The stability story: why the device kept resetting

This is the most interesting part of the build, and it's worth being precise about what was
actually established versus what was ruled out.

**Symptom.** The ESP8266 reset several times an hour in bursts, with 86–113 minutes of clean
uptime between bursts. From an API client the failures looked like `SocketClosedAPIError`,
`EncryptionHelloAPIError`, `HandshakeAPIError`, `TimeoutAPIError`.

**The discriminator that mattered:** ping kept answering at 1–2 ms the entire time, even while
every API handshake failed. ICMP on this device is served by the SDK/lwIP network stack, not
by the Arduino main loop — so a device that answers ping is not proven to be able to serve a
connection at all. That one fact is what kept the debugging honest instead of chasing "the
device is online, so it can't be a firmware fault."

Three plausible causes were raised and killed, each by a specific measurement:

| Hypothesis | Why it looked plausible | What killed it |
|---|---|---|
| HA holds the only API slot, and that's inherently unstable | Home Assistant was connected during every failure | Two clean runs, 86.7 min and 112.7 min, with HA connected and **idle** the whole time |
| Connection churn (reconnects, log streaming) crashes it | Every reset cluster coincided with *someone doing something* | That's confounded, not causal — flashing, watering tests and DEBUG log streaming all happened during the same windows |
| Power sag under load (pump/LED in-rush) | Textbook brownout shape | Measured 5.23V at the 5V input, **3.29V on 3V3**, 4.42V at the LED rings under load — a chronic droop would read under 3.0V. (A microsecond transient during WiFi TX is *not* ruled out — a multimeter can't see one — but 3.29V standing leaves little room for it to matter.) |

A planned bulk-capacitor mod (470µF + 0.1µF across 3V3) was designed and then **stood down**
once these measurements came in — its whole premise was a voltage problem the data didn't
support.

**Heap: what the evidence does and does not say.** An earlier version of this section said
heap was excluded as the mechanism. That went beyond the evidence and is retracted here,
because the retraction is more instructive than the claim was.

What holds: **total free heap at the crash was not anomalous.** The fresh reading at 00:16:20
was **6816 B**, squarely inside the **6.2-6.9 kB** band the device went on to run **12.8 hours
straight** in without incident. And before the `captive_portal` cut, 27 minutes of routine
sampling sat at **4.0-4.7 kB free** with no downward trend, so there is no leak. Total free
heap does not by itself explain the fault.

What does **not** hold is the sentence this section used to carry — "it crashed with 11.6 kB
contiguous, so it is not an allocation failure." That rested on reading one logged line as a
simultaneous snapshot. It is not one:

```
00:14:11  free=12000  block= 2992  frag=43%   just booted
00:14:30  free= 7152  block=11632  frag= 4%
00:15:00  free= 6872  block= 3408  frag=44%
00:16:20  free= 6816  block=11600  frag= 4%   <- the sample that got quoted
```

`block` is the largest contiguous free block, so it **cannot exceed** `free`. Those last two
columns do not belong to that `free` reading. The watcher joins three independently-updating
Home Assistant sensors and seeds each from its last known value rather than waiting for a
synchronised tick - deliberately, because an earlier version silently collected nothing for
45 minutes waiting for a sensor that had been byte-identical for over an hour. The cost of
that choice is visible here: `block=11600 / frag=4%` was measured just after boot, when free
really was around 12 kB, and only propagated once `free` had already fallen to 6.8 kB as Home
Assistant re-attached.

The consequence is uncomfortable and worth stating: **`max_block` at the moment of the crash
is unknown.** By the boot pattern it would have been back near the subscribed ~3176 B, not
11.6 kB. A Noise handshake needs a multi-kB *contiguous* buffer, and ~3 kB is exactly the
regime where that allocation starts to fail. So an allocation failure is **not excluded**. Nor
does `reset_reason` separate the two: an allocation failure that returns null and gets
dereferenced lands as an `Exception` just as a logic bug does.

**So the trigger is established and the mechanism is open.** A code fault in the handshake
path and an allocation failure are both still live. Separating them needs `max_block` sampled
at the fault itself, which this watcher cannot do — it would need per-field timestamps, or to
emit only when all three fields share a tick.

**The trigger, which is solid and mechanism-independent:** a *second* API client attempting a
Noise handshake while one was already attached crashes the device. `reset_reason` reads
`Exception` — an ESP8266 firmware fault, not a watchdog bite and not a brownout. The clearest
data point: 23 hours and 878 log lines with zero exception resets, then a second client was
deliberately connected — 3 exception resets followed in 3 minutes, each one 20–60 seconds
after a failed handshake attempt. Stopping the second client stopped the resets.

**The operational rule that follows:** exactly one API client, ever. Home Assistant holds it.
And there's a subtlety that costs real debugging time if you miss it — **stopping the other
client isn't enough on its own.** The device keeps its half of a dropped connection alive
until its own keepalive expires; connecting inside that window still counts as a second client
and still crashes it, confirmed by a reset that happened when a script connected three minutes
after the other side's socket had already closed.

**The fix that shipped:** removing `captive_portal:`, which pulls in a web server and DNS
server neither used in practice, freed 2008 B of static RAM (48900 → 46892 B) and 40922 B of
flash. The device then ran **12.8 hours continuously** with HA as the sole client — the control
run that everything else is measured against.

**One number worth carrying forward on its own:** adding the diagnostics that found all of
this — heap sensors, reset-reason reporting — cost about 655 B, roughly 0.8% of total RAM. On
a device with 3–4 kB free, that's a fifth of the remaining headroom. Measuring the edge moved
the edge.

**A second, unrelated lesson came out of the recorder that collected all this data, not the
device itself.** It originally ran under a service manager's "always restart" policy, driven
by a script with its own hard end time. Once that deadline passed, the script would exit
cleanly, the service manager would relaunch it, it would see the deadline already behind it,
and exit again — every few seconds, forever, a restart loop dressed up as a healthy service.
Fixed by switching to "restart on failure only." The general rule: an always-restart policy
belongs on something meant to run forever, not on a job that has a horizon.
