"""pyserial transport via serial_for_url (COM5, /dev/ttyUSB0, socket://). Owner: protocol-engineer."""

from __future__ import annotations

from typing import Any

from pytelemetry.core.transport.base import TransportError

__all__ = ["SerialTransport"]


class SerialTransport:
    """Lazy pyserial wrapper; import happens in open() so headless tests don't need the package."""

    def __init__(self, url: str, baud: int = 115200, timeout: float = 0.02) -> None:
        self._url = url
        self._baud = baud
        self._timeout = timeout
        self._ser: Any = None

    def open(self) -> None:
        import serial  # type: ignore[import-untyped]  # local import by design

        try:
            self._ser = serial.serial_for_url(
                self._url, baudrate=self._baud, timeout=self._timeout, write_timeout=1.0
            )
        except Exception as exc:  # pyserial raises several unrelated types
            raise TransportError(f"cannot open {self._url}: {exc}") from exc

    def close(self) -> None:
        if self._ser is not None:
            try:
                self._ser.close()
            finally:
                self._ser = None

    def read(self, max_bytes: int) -> bytes:
        if self._ser is None:
            return b""
        try:
            waiting = getattr(self._ser, "in_waiting", 0)
            return bytes(self._ser.read(max(1, min(max_bytes, waiting or 1))))
        except Exception:
            return b""

    def write(self, data: bytes) -> int:
        if self._ser is None:
            return 0
        try:
            return int(self._ser.write(data) or 0)
        except Exception:
            return 0

    @property
    def is_open(self) -> bool:
        return bool(self._ser is not None and getattr(self._ser, "is_open", False))
