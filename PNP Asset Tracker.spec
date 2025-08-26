# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['pnp_pyqt_app.py'],
    pathex=[],
    binaries=[],
    datas=[('main_window.ui', '.'), ('active_tab.ui', '.'), ('dispatched_tab.ui', '.'), ('receive_tab.ui', '.'), ('style.qss', '.'), ('config.ini', '.'), ('logic_league_logo.ico', '.')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='PNP Asset Tracker',
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
    icon=['logic_league_logo.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='PNP Asset Tracker',
)
