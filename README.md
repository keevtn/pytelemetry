# PyTelemetry

A desktop dashboard for watching and tuning microcontrollers over a serial port. It speaks the PyTelemetry v1
wire protocol (see `docs/PROTOCOL.md`): live telemetry in a table and on real-time plots, a device alert log,
read/write of firmware "live variables" by id, and CSV recording. Runs on Windows, macOS, and Linux.

The device-side C library in `firmware/` is copied byte-for-byte from the upstream project and is never
modified — the Python host is wire-compatible with hardware already running it.

## Install (from source)

Requires [uv](https://docs.astral.sh/uv/).

```bash
uv sync --all-extras
```

## Quick start

No hardware needed — run the built-in simulator and connect to it in one command:

```bash
uv run pytelemetry --sim
```

Pick a channel in the plot list on the left; it draws immediately. Open the Live Vars panel, change a value,
hit Apply, and watch it round-trip through the real protocol codec.

Other entry points:

```bash
uv run pytelemetry                                   # GUI, nothing connected
uv run pytelemetry --demo                            # GUI fed by a synthetic source (no protocol)
uv run pytelemetry --connect socket://127.0.0.1:5555 # connect to a device/sim at a URL
uv run pytelemetry --connect COM5                    # a real serial port (Windows)
uv run pytelemetry --connect /dev/ttyUSB0            # a real serial port (Linux/macOS)
uv run pytelemetry --self-test                       # headless: start sim + core, exit 0 if data flows
```

Run the simulator as a standalone server (for the two-process flow):

```bash
uv run pytelemetry-sim --port 5555
# then, elsewhere:
uv run pytelemetry --connect socket://127.0.0.1:5555
```

Use `127.0.0.1`, not `localhost` — on Windows `localhost` can resolve to IPv6 first and miss the server.

## Using it

- **Connect** — pick a port (or type a `socket://host:port` URL), choose baud, Connect. Shows live frames/s
  and dropped-frame count (hover for a per-reason breakdown).
- **Telemetry** — one row per channel; filter, sort, double-click a row to plot it. Stale rows dim after 2 s.
- **Plots** — select channels, follow/pause, choose the time window.
- **Alerts** — device events; firmware debug chatter is greyed and hidden behind a toggle.
- **Live Vars** — edit a firmware variable and Apply; values clamp to the limits in your config.
- **Recording** — Start writes a wide-format, host-timestamped CSV.
- **View menu** — reopen any panel you closed, or Reset Layout. Your layout is remembered between runs.

Live-variable names, units, and limits are supplied by `pytelemetry.toml` (the wire carries only numeric ids):

```toml
[connection]
port = "socket://127.0.0.1:5555"
baud = 115200

[[live_vars]]
id = 1
name = "Pitch"
unit = "deg"
min = -45.0
max = 45.0
```

## Build a standalone executable

```bash
uv run python packaging/build.py            # onedir  -> dist/PyTelemetry/
uv run python packaging/build.py --onefile  # single file
```

The executable is named `PyTelemetry`; the build also produces `dist/PyTelemetry-<os>-<arch>.zip`.

## Downloads

CI builds the three-OS executables on every push to `main` (see the **Actions** tab → latest run → Artifacts).
Tagged releases (`vX.Y.Z`) attach the zips to a GitHub Release.

## ESP32 / Arduino example

`firmware/examples/esp32_arduino/esp32_arduino.ino` is a minimal sketch that streams telemetry and exposes a
few live variables using the unmodified device library. Copy `firmware/*.c` and `firmware/*.h` alongside it (or
add `firmware/` to your library path), flash, then Connect to the board's serial port.

## Development

```bash
uv run pytest -q                 # full suite
uv run pytest -q -m "not soak"   # fast suite
uv run pytest -q -m soak         # throughput/memory soak
uv run ruff check . && uv run ruff format --check .
uv run mypy pytelemetry/core pytelemetry/sim
uv run python tools/gen_golden.py --check   # verify the Python codec still matches the C firmware (needs a C compiler)
```

## Troubleshooting

- **Linux: Qt fails to start** — install the platform libs: `libegl1 libgl1 libxkbcommon0 libdbus-1-3`. For
  headless/CI runs set `QT_QPA_PLATFORM=offscreen`.
- **Connection refused on `socket://localhost:...`** — use `127.0.0.1` instead (IPv6 resolution on Windows).
- **Permission denied on a serial port (Linux)** — add yourself to the `dialout` group and re-log in.

## Note on authorship

This project was built iteratively with AI assistance; all code is reviewed and tested, with the wire protocol
pinned to the firmware by the golden-vector suite.
