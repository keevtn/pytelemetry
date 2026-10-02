# PyInstaller spec for PyTelemetry. Owner: release-engineer.
# onedir by default; set PYI_ONEFILE=1 for a single-file build. Driven by packaging/build.py.

import os

block_cipher = None
onefile = os.environ.get("PYI_ONEFILE") == "1"

# pyserial loads URL handlers and the OS port lister dynamically, so PyInstaller can't see them.
# Without these the frozen app fails with: protocol 'socket' not known. pyqtgraph is handled by its
# own contrib hook, so we deliberately do NOT collect_submodules it (that pulls in the examples tree).
hiddenimports = [
    "serial.urlhandler.protocol_socket",
    "serial.urlhandler.protocol_loop",
    "serial.urlhandler.protocol_rfc2217",
    "serial.urlhandler.protocol_hwgrep",
    "serial.urlhandler.protocol_spy",
    "serial.urlhandler.protocol_alt",
    "serial.tools.list_ports",
]

a = Analysis(
    ["pytelemetry_main.py"],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "PyQt5", "PyQt6"],
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

if onefile:
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.zipfiles,
        a.datas,
        name="PyTelemetry",
        console=False,
        disable_windowed_traceback=False,
        upx=False,
    )
else:
    exe = EXE(
        pyz,
        a.scripts,
        name="PyTelemetry",
        console=False,
        upx=False,
        exclude_binaries=True,
    )
    coll = COLLECT(exe, a.binaries, a.zipfiles, a.datas, upx=False, name="PyTelemetry")
