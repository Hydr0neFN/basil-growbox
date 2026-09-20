"""Set the basil device's config numbers over the API.

Separate from watch-water.py because a `restore_value` number on the device
wins over the yaml's `initial_value` on a normal boot, so editing the yaml
alone changes nothing until a flash that happens to clear preferences -
which on ESP8266 is not guaranteed even then. Change both.

Usage:  python set-numbers.py "Stop at=55" "Water below=22"

Only run this when nothing else holds the API slot; the ESP8266 has very
few, and a handshake it cannot allocate for has taken the device down.
"""

import asyncio
import os
import re
import sys
import time

from aioesphomeapi import APIClient

HOST = os.environ.get("BASIL_HOST", "basil.local")
PORT = 6053


def read_key(path="secrets.yaml"):
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            m = re.match(r'\s*basil_api_key:\s*"?([^"\s]+)"?', line)
            if m:
                return m.group(1)
    raise SystemExit("basil_api_key not found in secrets.yaml")


async def main(pairs):
    cli = APIClient(HOST, PORT, None, noise_psk=read_key())
    wait = 5
    for _ in range(6):
        try:
            await cli.connect(login=True)
            break
        except Exception as exc:
            print(f"connect failed: {type(exc).__name__}, retry in {wait}s",
                  flush=True)
            await asyncio.sleep(wait)
            wait = min(wait * 2, 60)
    else:
        raise SystemExit("could not connect")

    entities, _ = await cli.list_entities_services()
    nums = {e.name: e for e in entities if type(e).__name__ == "NumberInfo"}

    for name, value in pairs:
        if name not in nums:
            raise SystemExit(f"number {name!r} not found. Saw: "
                             f"{sorted(nums)}")
        cli.number_command(nums[name].key, value)
        print(f"set {name} = {value}", flush=True)
        await asyncio.sleep(1)

    # Read back rather than trust the write: these are optimistic entities,
    # so the command is acknowledged locally whether or not it landed.
    seen = {}

    def on_state(st):
        for n, info in nums.items():
            if info.key == getattr(st, "key", None):
                seen[n] = getattr(st, "state", None)

    cli.subscribe_states(on_state)
    await asyncio.sleep(4)
    for name, value in pairs:
        got = seen.get(name)
        ok = got is not None and abs(got - value) < 0.001
        print(f"  readback {name}: {got}  {'OK' if ok else 'MISMATCH'}",
              flush=True)

    await cli.disconnect()


if __name__ == "__main__":
    args = []
    for a in sys.argv[1:]:
        k, _, v = a.partition("=")
        args.append((k, float(v)))
    if not args:
        raise SystemExit(__doc__)
    asyncio.run(main(args))
