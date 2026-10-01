"""socket:// simulator server. Owner: test-engineer.

Serves one or more clients a live PyTelemetry device: a FakeDevice (exact firmware behaviour) plus scripted
telemetry from channels.py. The host connects with serial_for_url("socket://host:port"). Headless, stdlib
sockets only — no Qt, no pyserial on the server side.
"""

from __future__ import annotations

import logging
import socket
import threading
import time

from pytelemetry.sim.channels import DEFAULT_LIVE_VARS, Channel, default_channels
from pytelemetry.sim.fake_device import FakeDevice

__all__ = ["SimServer"]

_log = logging.getLogger(__name__)


class SimServer:
    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 5555,
        channels: list[Channel] | None = None,
        rate_hz: float = 50.0,
    ) -> None:
        self._host = host
        self._port = port
        self._channels = channels if channels is not None else default_channels()
        self._interval = 1.0 / rate_hz
        self._sock: socket.socket | None = None
        self._stop = threading.Event()
        self._threads: list[threading.Thread] = []

    @property
    def port(self) -> int:
        return self._port

    def start(self) -> None:
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind((self._host, self._port))
        self._port = self._sock.getsockname()[1]  # resolve port 0 -> actual
        self._sock.listen(4)
        self._sock.settimeout(0.2)
        t = threading.Thread(target=self._accept_loop, name="sim-accept", daemon=True)
        t.start()
        self._threads.append(t)

    def stop(self) -> None:
        self._stop.set()
        if self._sock is not None:
            self._sock.close()
            self._sock = None
        for t in self._threads:
            t.join(timeout=1.0)

    def _accept_loop(self) -> None:
        assert self._sock is not None
        while not self._stop.is_set():
            try:
                conn, _addr = self._sock.accept()
            except (TimeoutError, OSError):
                continue
            t = threading.Thread(target=self._serve, args=(conn,), name="sim-client", daemon=True)
            t.start()
            self._threads.append(t)

    def _serve(self, conn: socket.socket) -> None:
        conn.settimeout(0.02)
        device = FakeDevice()
        for var_id, vtype, value, _name, _unit in DEFAULT_LIVE_VARS:
            device.register_live(var_id, vtype, value)
        last = {ch.key: 0.0 for ch in self._channels}
        start = time.monotonic()
        try:
            while not self._stop.is_set():
                # 1) drain any host bytes -> device, write its replies
                try:
                    data = conn.recv(4096)
                    if data == b"":
                        return  # client closed
                    for frame in device.feed(data):
                        conn.sendall(frame)
                except TimeoutError:
                    pass
                except OSError:
                    return
                # 2) emit scheduled scripted telemetry
                now = time.monotonic()
                t = now - start
                for ch in self._channels:
                    if now - last[ch.key] >= ch.period_s:
                        last[ch.key] = now
                        key, vtype, value = ch.sample(t)
                        for frame in device.telemetry(key, vtype, value):
                            try:
                                conn.sendall(frame)
                            except OSError:
                                return
                time.sleep(self._interval)
        finally:
            try:
                conn.close()
            except OSError:
                pass


def serve(port: int = 5555) -> None:
    """Blocking entry point for `pytelemetry-sim`."""
    server = SimServer(port=port)
    server.start()
    _log.info("simulator listening on socket://127.0.0.1:%d", server.port)
    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        server.stop()
