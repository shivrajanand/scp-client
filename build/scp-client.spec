# -*- mode: python ; coding: utf-8 -*-
#
# PyInstaller spec for SCP Transfer Client
#
# Build from the project root with:
#     pyinstaller build/scp-client.spec
#
# Result:
#     dist/SCPTransferClient.exe

from pathlib import Path

block_cipher = None

project_root = Path(SPECPATH).parent

a = Analysis(
    [str(project_root / "main.py")],
    pathex=[str(project_root)],
    binaries=[],
    datas=[
        (str(project_root / "assets"), "assets"),
    ],
    hiddenimports=[
        "paramiko",
        "scp",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(
    a.pure,
    a.zipped_data,
    cipher=block_cipher,
)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    a.zipfiles,
    name="SCPTransferClient",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=(
        str(project_root / "assets" / "icons" / "app.ico")
        if (project_root / "assets" / "icons" / "app.ico").exists()
        else None
    ),
)