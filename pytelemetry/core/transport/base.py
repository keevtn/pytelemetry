"""Transport base. Owner: protocol-engineer."""

from __future__ import annotations

from pytelemetry.core.interfaces import Transport

__all__ = ["Transport", "TransportError"]


class TransportError(Exception):
    """Open/IO failure on a transport. Session surfaces it; hot-path code never raises."""
