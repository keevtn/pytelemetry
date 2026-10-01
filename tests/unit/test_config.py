"""Config load/save round-trip. Owner: core-engineer."""

from __future__ import annotations

from pathlib import Path

from pytelemetry.core.config import load_config, save_config
from pytelemetry.core.types import AppConfig, ChannelConfig


def test_missing_file_returns_defaults(tmp_path: Path) -> None:
    cfg = load_config(tmp_path / "nope.toml")
    assert cfg.baud == 115200
    assert cfg.live_vars == ()


def test_round_trip(tmp_path: Path) -> None:
    original = AppConfig(
        port="socket://localhost:5555",
        baud=115200,
        history_samples=50_000,
        live_vars=(
            ChannelConfig(1, "Pitch", "deg", -45.0, 45.0),
            ChannelConfig(2, "Gain", ""),
        ),
    )
    path = tmp_path / "pytelemetry.toml"
    save_config(original, path)
    loaded = load_config(path)
    assert loaded.port == original.port
    assert loaded.history_samples == 50_000
    assert loaded.live_vars[0] == ChannelConfig(1, "Pitch", "deg", -45.0, 45.0)
    assert loaded.live_vars[1].name == "Gain"


def test_live_var_names_are_host_side_only(tmp_path: Path) -> None:
    # Names/units/limits come from config, never the wire (PROTOCOL.md section 4).
    path = tmp_path / "c.toml"
    save_config(AppConfig(live_vars=(ChannelConfig(7, "Throttle", "%", 0.0, 100.0),)), path)
    text = path.read_text()
    assert "Throttle" in text and "id = 7" in text
