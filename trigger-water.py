"""Press the Basil device's "Water now" button and stream its log.

Reads the API key from secrets.yaml so it never appears in a command line.
Usage:  python trigger-water.py [seconds] [dose_cm]
        seconds  how long to stay connected and stream logs (default 1200)
        dose_cm  optional: set the Dose number before pressing. It is a
                 restore_value entity, so reflashing will not change it -
                 this is the only way to move it without Home Assistant.

The ESP8266 accepts very few simultaneous API clients, so this competes
with Home Assistant's session. Run it, watch, and let it exit.
"""

import asyncio
import os
import re
import sys
import time

from aioesphomeapi import APIClient
from aioesphomeapi.model import LogLevel

HOST = os.environ.get("BASIL_HOST", "basil.local")
PORT = 6053
BUTTON = "Water now"
DOSE = "Dose"


def read_key(path="secrets.yaml"):
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            m = re.match(r'\s*basil_api_key:\s*"?([^"\s]+)"?', line)
            if m:
                return m.group(1)
    raise SystemExit("basil_api_key not found in secrets.yaml")


def stamp():
    return time.strftime("%H:%M:%S")


async def main(run_for, dose=None):
    cli = APIClient(HOST, PORT, None, noise_psk=read_key())

    # The ESP8266 has very few API slots and Home Assistant holds one, so a
    # cold connect often gets EOF at the hello/login stage. Retry rather
    # than treat it as a failure.
    for attempt in range(1, 9):
        try:
            await cli.connect(login=True)
            break
        except Exception as exc:
            print(f"[{stamp()}] connect {attempt}/8 failed: "
                  f"{type(exc).__name__}", flush=True)
            await asyncio.sleep(5)
    else:
        raise SystemExit("could not get an API slot - is esphome logs or "
                         "another client connected?")
    print(f"[{stamp()}] connected to {HOST}", flush=True)

    entities, _ = await cli.list_entities_services()
    target = None
    for group in entities:
        name = getattr(group, "name", None)
        if name == BUTTON and type(group).__name__ == "ButtonInfo":
            target = group
            break
    if target is None:
        names = sorted({getattr(e, "name", "?") for e in entities})
        raise SystemExit(f"button {BUTTON!r} not found. Saw: {names}")

    if dose is not None:
        num = next((e for e in entities
                    if getattr(e, "name", None) == DOSE
                    and type(e).__name__ == "NumberInfo"), None)
        if num is None:
            raise SystemExit("Dose number entity not found")
        cli.number_command(num.key, dose)
        print(f"[{stamp()}] Dose set to {dose} cm", flush=True)
        await asyncio.sleep(2)

    def on_log(msg):
        line = msg.message
        if isinstance(line, bytes):
            line = line.decode("utf-8", "replace")
        print(f"[{stamp()}] {line.rstrip()}", flush=True)

    # Pass the level explicitly: without it the last run streamed nothing.
    cli.subscribe_logs(on_log, log_level=LogLevel.LOG_LEVEL_DEBUG)
    await asyncio.sleep(2)

    print(f"[{stamp()}] >>> pressing {BUTTON!r}", flush=True)
    cli.button_command(target.key)

    await asyncio.sleep(run_for)
    print(f"[{stamp()}] window over, disconnecting", flush=True)
    await cli.disconnect()


if __name__ == "__main__":
    secs = int(sys.argv[1]) if len(sys.argv) > 1 else 1200
    dose = float(sys.argv[2]) if len(sys.argv) > 2 else None
    asyncio.run(main(secs, dose))
