"""pytelemetry.toml config load/save. Owner: core-engineer.

Live-var names/units/limits live here, not on the wire (PROTOCOL.md section 4). Read with stdlib tomllib,
write with tomli-w. Missing file -> defaults; a malformed file raises so the user sees it at startup.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import tomli_w

from pytelemetry.core.types import AppConfig, ChannelConfig

__all__ = ["DEFAULT_PATH", "load_config", "save_config"]

DEFAULT_PATH = Path("pytelemetry.toml")


def load_config(path: str | Path = DEFAULT_PATH) -> AppConfig:
    p = Path(path)
    if not p.exists():
        return AppConfig()
    raw = tomllib.loads(p.read_text(encoding="utf-8"))
    conn = raw.get("connection", {})
    vars_raw = raw.get("live_vars", [])
    live = tuple(
        ChannelConfig(
            id=int(entry["id"]),
            name=str(entry.get("name", f"var{entry['id']}")),
            unit=str(entry.get("unit", "")),
            minimum=_opt_float(entry.get("min")),
            maximum=_opt_float(entry.get("max")),
        )
        for entry in vars_raw
    )
    return AppConfig(
        port=str(conn.get("port", "")),
        baud=int(conn.get("baud", 115200)),
        history_samples=int(raw.get("history", {}).get("samples", 100_000)),
        live_vars=live,
    )


def save_config(config: AppConfig, path: str | Path = DEFAULT_PATH) -> None:
    doc: dict[str, object] = {
        "connection": {"port": config.port, "baud": config.baud},
        "history": {"samples": config.history_samples},
        "live_vars": [
            {
                k: v
                for k, v in (
                    ("id", c.id),
                    ("name", c.name),
                    ("unit", c.unit),
                    ("min", c.minimum),
                    ("max", c.maximum),
                )
                if v is not None and v != ""
            }
            for c in config.live_vars
        ],
    }
    Path(path).write_text(tomli_w.dumps(doc), encoding="utf-8")


def _opt_float(value: object) -> float | None:
    return None if value is None else float(value)  # type: ignore[arg-type]
