# -*- mode: python ; coding: utf-8 -*-
# 云极智能拆版 · PyInstaller 打包配置（Windows onefile）
a = Analysis(
    ['app.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('samples', 'samples'),
        ('brand', 'brand'),
    ],
    hiddenimports=[
        'cv2',
        'shapely',
        'PIL',
        'qrcode',
        'pytoshop',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib'],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='云极智能拆版V1.2',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    icon='icon.ico',
)
