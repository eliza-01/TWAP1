# -*- mode: python ; coding: utf-8 -*-

import os
from pathlib import Path
from PyInstaller.utils.hooks import collect_all

ROOT = Path(SPECPATH).parents[1]
EXE_NAME = os.getenv("TWAP_EXE_NAME", "TWAPs")
ASSET_DIR = ROOT / "client_desktop" / "assets"
ICON_ICO = ASSET_DIR / "twaps_icon.ico"
ICON_PNG = ASSET_DIR / "twaps_icon_256.png"

webview_datas, webview_binaries, webview_hiddenimports = collect_all("webview")
pystray_datas, pystray_binaries, pystray_hiddenimports = collect_all("pystray")
pil_datas, pil_binaries, pil_hiddenimports = collect_all("PIL")

asset_datas = []
if ICON_PNG.exists():
    asset_datas.append((str(ICON_PNG), "client_desktop/assets"))
if ICON_ICO.exists():
    asset_datas.append((str(ICON_ICO), "client_desktop/assets"))

hiddenimports = webview_hiddenimports + pystray_hiddenimports + pil_hiddenimports + [
    "client_desktop.build_config_generated",
    "webview.platforms.edgechromium",
    "pystray._win32",
    "PIL.Image",
    "uvicorn.config",
    "uvicorn.logging",
    "uvicorn.lifespan.on",
    "uvicorn.loops.auto",
    "uvicorn.loops.asyncio",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.http.h11_impl",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.protocols.websockets.websockets_impl",
]


a = Analysis(
    [str(ROOT / "client_desktop" / "wv2_client.py")],
    pathex=[str(ROOT)],
    binaries=webview_binaries + pystray_binaries + pil_binaries,
    datas=webview_datas + pystray_datas + pil_datas + asset_datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "PyQt5", "PyQt6", "PySide2", "PySide6", "qtpy"],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name=EXE_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ICON_ICO) if ICON_ICO.exists() else None,
)
