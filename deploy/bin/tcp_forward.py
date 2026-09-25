#!/usr/bin/env python3
"""Minimal TCP forwarder: bind the Tailscale IPv4 address and relay to a loopback port.

Rootless Docker cannot publish on the Tailscale interface and `tailscale serve`
needs root, so this user-level relay exposes ntfy to tailnet devices only.
"""
import argparse
import asyncio
import subprocess


async def pipe(reader, writer):
    try:
        while data := await reader.read(65536):
            writer.write(data)
            await writer.drain()
    except (ConnectionError, asyncio.CancelledError):
        pass
    finally:
        writer.close()


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--listen-tailscale', action='store_true')
    ap.add_argument('--listen', default=None)
    ap.add_argument('--port', type=int, required=True)
    ap.add_argument('--target', required=True)
    a = ap.parse_args()
    host = a.listen
    if a.listen_tailscale:
        host = subprocess.run(['tailscale', 'ip', '-4'], capture_output=True, text=True,
                              check=True).stdout.split()[0]
    if not host or not host.startswith('100.'):
        raise SystemExit('refusing to bind a non-tailnet address')
    thost, tport = a.target.rsplit(':', 1)

    async def handle(r, w):
        try:
            tr, tw = await asyncio.open_connection(thost, int(tport))
        except OSError:
            w.close()
            return
        await asyncio.gather(pipe(r, tw), pipe(tr, w))

    server = await asyncio.start_server(handle, host, a.port)
    async with server:
        await server.serve_forever()


if __name__ == '__main__':
    asyncio.run(main())
