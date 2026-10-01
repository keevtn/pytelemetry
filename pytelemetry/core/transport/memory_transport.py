"""In-memory transport pair for tests and the simulator. Owner: protocol-engineer."""

from __future__ import annotations

import threading

__all__ = ["MemoryTransport", "memory_pair"]


class _Pipe:
    def __init__(self) -> None:
        self.buf = bytearray()
        self.cond = threading.Condition()
        self.closed = False


class MemoryTransport:
    """One endpoint of a bidirectional in-memory pipe. Thread-safe; read() blocks up to `timeout`."""

    def __init__(self, rx: _Pipe, tx: _Pipe, timeout: float = 0.02) -> None:
        self._rx = rx
        self._tx = tx
        self._timeout = timeout
        self._open = False

    def open(self) -> None:
        self._open = True

    def close(self) -> None:
        self._open = False
        for pipe in (self._rx, self._tx):
            with pipe.cond:
                pipe.closed = True
                pipe.cond.notify_all()

    def read(self, max_bytes: int) -> bytes:
        with self._rx.cond:
            if not self._rx.buf and not self._rx.closed:
                self._rx.cond.wait(self._timeout)
            data = bytes(self._rx.buf[:max_bytes])
            del self._rx.buf[: len(data)]
            return data

    def write(self, data: bytes) -> int:
        if not self._open:
            return 0
        with self._tx.cond:
            if self._tx.closed:
                return 0
            self._tx.buf += data
            self._tx.cond.notify_all()
        return len(data)

    @property
    def is_open(self) -> bool:
        return self._open


def memory_pair(timeout: float = 0.02) -> tuple[MemoryTransport, MemoryTransport]:
    """(host_end, device_end) cross-connected."""
    a, b = _Pipe(), _Pipe()
    return MemoryTransport(a, b, timeout), MemoryTransport(b, a, timeout)
