# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for Orchestra
#
# Build with:
#   pyinstaller orchestra.spec

from PyInstaller.utils.hooks import collect_submodules

# dnspython is used by eventlet for DNS; all rdtypes sub-packages must be
# included explicitly because PyInstaller misses them during static analysis.
_dns_imports = collect_submodules('dns')
# Also collect all eventlet submodules to cover any dynamically-loaded hubs.
_eventlet_imports = collect_submodules('eventlet')
#
# Output: dist/Orchestra/Orchestra.exe  (folder distribution)

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        # Bundle the Flask/mobile static files
        ('orchestra/static', 'orchestra/static'),
        # Bundle the Qt toolbar icons
        ('orchestra/ui/icons', 'orchestra/ui/icons'),
    ],
    hiddenimports=[
        # ----------------------------------------------------------------
        # eventlet — hubs and green modules used at runtime
        # ----------------------------------------------------------------
        'eventlet.hubs.epolls',
        'eventlet.hubs.kqueue',
        'eventlet.hubs.selects',
        'eventlet.queue',
        'eventlet.timeout',
        'eventlet.wsgi',
        'eventlet.websocket',
        'eventlet.greenpool',
        'eventlet.greenthread',
        'eventlet.corolocal',
        'eventlet.debug',
        'eventlet.event',
        'eventlet.pools',
        'eventlet.semaphore',
        'eventlet.backdoor',
        'eventlet.support',
        'eventlet.green.select',
        'eventlet.green.ssl',
        'eventlet.green.socket',
        'eventlet.green.thread',
        'eventlet.green.time',
        'eventlet.green.threading',
        'eventlet.green.subprocess',
        # ----------------------------------------------------------------
        # Flask / SocketIO / engineio
        # ----------------------------------------------------------------
        'engineio.async_drivers.eventlet',
        'flask_socketio',
        'socketio',
        'engineio',
        'bidict',
        'simple_websocket',
        # ----------------------------------------------------------------
        # pywin32 — COM PowerPoint control
        # ----------------------------------------------------------------
        'win32api',
        'win32con',
        'win32com',
        'win32com.client',
        'win32com.server',
        'pythoncom',
        'pywintypes',
        # ----------------------------------------------------------------
        # python-pptx — import helper
        # ----------------------------------------------------------------
        'pptx',
        'pptx.oxml',
        'pptx.oxml.ns',
        'pptx.util',
        'lxml',
        'lxml.etree',
        'lxml._elementpath',
        # ----------------------------------------------------------------
        # qrcode / Pillow
        # ----------------------------------------------------------------
        'qrcode',
        'qrcode.image.pil',
        'qrcode.image.svg',
        'PIL',
        'PIL.Image',
        'PIL.ImageDraw',
        # ----------------------------------------------------------------
        # PyQt6
        # ----------------------------------------------------------------
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.QtWidgets',
        'PyQt6.QtNetwork',
        'PyQt6.sip',
        # ----------------------------------------------------------------
        # stdlib modules that eventlet may hide from the analyser
        # ----------------------------------------------------------------
        'encodings',
        'encodings.utf_8',
        'encodings.ascii',
        '_ssl',
        'select',
    ] + _dns_imports + _eventlet_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'numpy',
        'scipy',
        'IPython',
        'jupyter',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Orchestra',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,       # UPX can break PyQt6 DLLs on Windows
    console=False,   # No terminal window — GUI app
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='Orchestra',
)
