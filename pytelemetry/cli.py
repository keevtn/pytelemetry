"""Entry points: pytelemetry (GUI), pytelemetry-sim, pytelemetry --self-test. Owner: lead."""

from __future__ import annotations

import argparse
import logging
import sys
import time

__all__ = ["main", "sim_main", "self_test"]

_log = logging.getLogger(__name__)


def sim_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pytelemetry-sim", description="Simulated PyTelemetry device.")
    parser.add_argument("--port", type=int, default=5555, help="TCP port for socket:// (default 5555)")
    parser.add_argument("--rate", type=float, default=50.0, help="telemetry frames/sec (default 50)")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    from pytelemetry.sim.server import SimServer

    server = SimServer(port=args.port, rate_hz=args.rate)
    server.start()
    _log.info("simulator on socket://127.0.0.1:%d (Ctrl-C to stop)", server.port)
    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        server.stop()
    return 0


def self_test(timeout_s: float = 10.0) -> int:
    """Headless: spin up the sim, connect the core pipeline over socket://, confirm data flows. Exit 0/1.

    UI wiring joins this in M3 (offscreen pytest-qt); for now it proves the sim + session + store path.
    """
    from pytelemetry.core.session import Session
    from pytelemetry.core.store import TelemetryStore
    from pytelemetry.core.transport.serial_transport import SerialTransport
    from pytelemetry.sim.server import SimServer

    server = SimServer(port=0, rate_hz=100.0)
    server.start()
    store = TelemetryStore(history_samples=10_000)
    session = Session(SerialTransport(f"socket://127.0.0.1:{server.port}"))
    session.add_sink(store)
    session.start()
    try:
        session.request_live_data()
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            if store.keys() and store.live_vars():
                _log.info("self-test OK: channels=%s live_vars=%d", store.keys(), len(store.live_vars()))
                return 0
            time.sleep(0.05)
        _log.error("self-test FAILED: no data within %.1fs", timeout_s)
        return 1
    finally:
        session.stop()
        server.stop()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pytelemetry", description="PyTelemetry dashboard.")
    parser.add_argument("--connect", metavar="URL", help="serial url, e.g. COM5 or socket://host:port")
    parser.add_argument("--demo", action="store_true", help="run against the built-in synthetic source")
    parser.add_argument("--self-test", action="store_true", help="headless self-test, exit 0 on success")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    if args.self_test:
        return self_test()

    try:
        from pytelemetry.ui.app import run_app
    except NotImplementedError:
        _log.error("the GUI lands in M3; use `pytelemetry --self-test` or `pytelemetry-sim` for now")
        return 2
    return run_app(connect=args.connect, demo=args.demo)


if __name__ == "__main__":
    sys.exit(main())
