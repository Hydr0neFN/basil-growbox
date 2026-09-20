"""Trigger one watering cycle and keep its log even across dropped links.

Why this exists instead of trigger-water.py: the ESP8266 has very few API
slots and Home Assistant holds one, retrying every couple of seconds. Every
capture attempt so far died partway with WinError 64 / SocketClosedAPIError
and took the rest of the cycle with it. The device kept watering fine - only
the observer fell over. So this reconnects and re-subscribes on every drop,
and presses the button exactly once, on the first connection only.

Usage:  python watch-water.py [seconds] [dose_cm]
        seconds  total wall-clock window (default 4200 = 70 min, which
                 covers 5 cycles of fill + 3min drain + 10min soak)
        dose_cm  optional, sets the Dose number before the single press

Everything is appended to water-run2.log as well as printed, so a crash of
this script does not lose what was already seen.
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
LOGFILE = "water-run2.log"


def read_key(path="secrets.yaml"):
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            m = re.match(r'\s*basil_api_key:\s*"?([^"\s]+)"?', line)
            if m:
                return m.group(1)
    raise SystemExit("basil_api_key not found in secrets.yaml")


_log = open(LOGFILE, "a", encoding="utf-8", buffering=1)


def emit(text):
    line = f"[{time.strftime('%H:%M:%S')}] {text}"
    print(line, flush=True)
    _log.write(line + "\n")


ANSI = re.compile(r"\x1b\[[0-9;]*m")


async def session(key, press, deadline, backoff):
    """One connected stretch. Returns True if the button was pressed here.

    `backoff` is a one-element list holding the current retry delay. It is
    owned by the caller so that it survives across sessions: keeping it
    local reset it to the floor on every re-entry, which turned the outer
    retry loop back into a ~8s hammer no matter what the inner one did.
    """
    cli = APIClient(HOST, PORT, None, noise_psk=key)

    # Back off instead of hammering. A fixed ~6s retry put a Noise
    # handshake on the device every few seconds, and the recorder shows
    # three resets (23:23:35, 23:24:30, 23:25:44 on 2026-09-18) inside
    # exactly that window, with the device then staying up the moment the
    # loop stopped. Not proof - reset_reason will settle it - but a tight
    # retry loop is the worst thing to aim at a device that may be dying
    # of connection churn, and costs nothing to soften.
    while time.time() < deadline:
        try:
            await cli.connect(login=True)
            backoff[0] = 5          # only a real connection clears it
            break
        except Exception as exc:
            emit(f"connect failed: {type(exc).__name__} "
                 f"(next try in {backoff[0]}s)")
            await asyncio.sleep(backoff[0])
            backoff[0] = min(backoff[0] * 2, 60)
    else:
        return False

    emit(f"=== connected to {HOST} ===")

    dropped = asyncio.Event()

    def on_log(msg):
        line = msg.message
        if isinstance(line, bytes):
            line = line.decode("utf-8", "replace")
        emit(ANSI.sub("", line.rstrip()))

    cli.subscribe_logs(on_log, log_level=LogLevel.LOG_LEVEL_DEBUG)
    await asyncio.sleep(1)

    pressed = False
    if press:
        entities, _ = await cli.list_entities_services()
        if DOSE_SET[0] is not None:
            num = next((e for e in entities
                        if getattr(e, "name", None) == DOSE
                        and type(e).__name__ == "NumberInfo"), None)
            if num is None:
                raise SystemExit("Dose number entity not found")
            cli.number_command(num.key, DOSE_SET[0])
            emit(f">>> Dose set to {DOSE_SET[0]} cm")
            await asyncio.sleep(2)

        target = next((e for e in entities
                       if getattr(e, "name", None) == BUTTON
                       and type(e).__name__ == "ButtonInfo"), None)
        if target is None:
            raise SystemExit(f"button {BUTTON!r} not found")
        emit(f">>> pressing {BUTTON!r}")
        cli.button_command(target.key)
        pressed = True

    # Poll the link rather than trusting a callback: a half-open socket on
    # Windows shows up as the connection object flipping, not as an event.
    while time.time() < deadline:
        await asyncio.sleep(2)
        if not cli._connection or not cli._connection.is_connected:
            emit("!!! link dropped - will reconnect and keep listening")
            break
    else:
        emit("=== window over ===")
        dropped.set()

    try:
        await cli.disconnect()
    except Exception:
        pass
    return pressed


DOSE_SET = [None]


async def main(run_for, dose=None):
    DOSE_SET[0] = dose
    key = read_key()
    deadline = time.time() + run_for
    emit(f"### run start, window {run_for}s "
         f"(ends {time.strftime('%H:%M:%S', time.localtime(deadline))}) ###")

    press = True
    backoff = [5]
    while time.time() < deadline:
        try:
            if await session(key, press, deadline, backoff):
                press = False   # never press twice
        except Exception as exc:
            emit(f"session error: {type(exc).__name__}: {exc}")
            backoff[0] = min(backoff[0] * 2, 60)
        if time.time() < deadline:
            await asyncio.sleep(backoff[0])

    emit("### run end ###")


if __name__ == "__main__":
    secs = int(sys.argv[1]) if len(sys.argv) > 1 else 4200
    d = float(sys.argv[2]) if len(sys.argv) > 2 else None
    asyncio.run(main(secs, d))
