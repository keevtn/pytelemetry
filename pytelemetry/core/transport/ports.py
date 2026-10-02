"""Serial port enumeration for the Connect panel. Owner: protocol-engineer."""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["PortInfo", "list_ports"]


@dataclass(frozen=True, slots=True)
class PortInfo:
    device: str
    description: str


def list_ports() -> list[PortInfo]:
    try:
        from serial.tools import list_ports  # type: ignore[import-untyped]
    except ImportError:
        return []
    return [PortInfo(p.device, p.description or "") for p in sorted(list_ports.comports())]
