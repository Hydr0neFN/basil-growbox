# OTA: the measured upload procedure

The one-API-client rule in [the stability story](stability.md) applies to OTA too. The
measured procedure is worth stating exactly, because getting the timing wrong costs an OTA
attempt, not just a connection retry:

1. Block Home Assistant's connection to the device.
2. Wait for its side of the socket to clear (~80s).
3. Wait a *further* ~2 minutes for the device's own keepalive on that dropped connection to
   expire.
4. Upload.

Connecting inside that second window still counts as a second client and can reset the device
mid-upload. Done in that order, a real upload completed in **18.34 seconds, clean, first try**
— against two failed attempts the night before (61% and 16% progress) while HA was still
attached. Lift whatever block you used immediately after, and check the next light-schedule
boundary before opening that window at all, since Home Assistant loses control of the relay for
as long as it's blocked.

Treat that ~2-minute figure as the shortest wait that has actually worked, not a guaranteed
threshold: a separate measurement elsewhere in this project recorded a reset when a client
connected exactly three minutes after the other side's socket had cleared. The two data points
don't fully agree on where the safe line is — when in doubt, wait longer than 2 minutes.
