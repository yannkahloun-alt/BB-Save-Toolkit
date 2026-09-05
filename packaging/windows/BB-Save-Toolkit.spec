# PyInstaller one-directory build for the Windows local application.
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

ROOT = Path(SPECPATH).resolve().parents[1]

analysis = Analysis(
    [str(ROOT / "bb_windows.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        (str(ROOT / "config"), "config"),
        (str(ROOT / "references"), "references"),
        (str(ROOT / "bbtool" / "app" / "static"), "bbtool/app/static"),
    ],
    hiddenimports=collect_submodules("bbtool"),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(analysis.pure)
exe = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="BB-Save-Toolkit",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
)
collection = COLLECT(
    exe,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=False,
    name="BB-Save-Toolkit",
)
