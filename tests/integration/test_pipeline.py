"""End-to-end headless pipeline over memory and socket transports. Owner: test-engineer."""

from __future__ import annotations

import threading
import time

from pytelemetry.core.session import Session
from pytelemetry.core.store import TelemetryStore
from pytelemetry.core.transport.memory_transport import memory_pair
from pytelemetry.core.types import ChannelConfig, PacketType, ValueType
from pytelemetry.sim.channels import DEFAULT_LIVE_VARS
from pytelemetry.sim.fake_device import FakeDevice


def _device_with_defaults() -> FakeDevice:
    d = FakeDevice()
    for var_id, vtype, value, _name, _unit in DEFAULT_LIVE_VARS:
        d.register_live(var_id, vtype, value)
    return d


def _pump(dev_end, device: FakeDevice, stop: threading.Event) -> None:
    while not stop.is_set():
        data = dev_end.read(4096)
        if data:
            for frame in device.feed(data):
                dev_end.write(frame)


def test_session_over_memory_live_data_and_modify(capture_sink) -> None:
    host_end, dev_end = memory_pair(timeout=0.02)
    dev_end.open()
    device = _device_with_defaults()
    stop = threading.Event()
    threading.Thread(target=_pump, args=(dev_end, device, stop), daemon=True).start()

    cfg = {1: ChannelConfig(1, "Pitch", "deg")}
    session = Session(host_end, live_var_config=cfg)
    session.add_sink(capture_sink)
    session.start()
    try:
        session.request_live_data()
        session.modify_live_var(1, ValueType.FLOAT, 3.25)
        _wait(lambda: device.live_value(1) == 3.25)
    finally:
        session.stop()
        stop.set()

    assert capture_sink.live is not None
    assert capture_sink.live[0].id == 1 and capture_sink.live[0].name == "Pitch"
    assert device.live_value(1) == 3.25
    assert any(a.message == "Live Data Requested" and a.debug for a in capture_sink.alerts)
    assert capture_sink.stats is not None and capture_sink.stats.frames_ok > 0


def test_session_over_socket_gets_scripted_telemetry(sim_server) -> None:
    import socket

    from pytelemetry.core.protocol import codec
    from pytelemetry.core.protocol.framer import StreamFramer

    conn = socket.create_connection(("127.0.0.1", sim_server.port), timeout=2.0)
    conn.sendall(codec.encode_request_live_data())
    framer = StreamFramer()
    frames = []
    deadline = time.time() + 2.0
    while time.time() < deadline:
        conn.settimeout(0.2)
        try:
            data = conn.recv(4096)
        except (TimeoutError, OSError):
            data = b""
        if data:
            frames += framer.feed(data)
        has_live = any(f.header.packet_type == PacketType.RESPONSE_LIVE_DATA for f in frames)
        if has_live and sum(f.header.packet_type == PacketType.TELEMETRY for f in frames) > 4:
            break
    conn.close()

    live = [f for f in frames if f.header.packet_type == PacketType.RESPONSE_LIVE_DATA]
    assert live and codec.parse_live_data(live[0].value) == (
        (1, 2, 3.0),
        (2, 1, 10),
        (3, 3, True),
        (4, 0, 4000),
    )
    tele_keys = {f.key.decode() for f in frames if f.header.packet_type == PacketType.TELEMETRY} - {
        "CalculuatedCRC",
        "ReceivedCRC",
    }
    assert "Voltage" in tele_keys and "RPM" in tele_keys


def test_store_fills_from_session(capture_sink) -> None:
    host_end, dev_end = memory_pair(timeout=0.02)
    dev_end.open()
    device = _device_with_defaults()
    stop = threading.Event()
    threading.Thread(target=_pump, args=(dev_end, device, stop), daemon=True).start()

    store = TelemetryStore(history_samples=1000)
    session = Session(host_end)
    session.add_sink(store)
    session.start()
    try:
        for i in range(20):
            device_frame = device.telemetry("Voltage", ValueType.FLOAT, 12.0 + i * 0.1)
            for f in device_frame:
                dev_end.write(f)
        _wait(lambda: len(store.history("Voltage")[0]) >= 20)
    finally:
        session.stop()
        stop.set()

    times, values = store.history("Voltage")
    assert len(values) >= 20
    assert store.latest("Voltage") is not None


def _wait(cond, timeout: float = 2.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if cond():
            return
        time.sleep(0.005)
    raise AssertionError("condition not met within timeout")
