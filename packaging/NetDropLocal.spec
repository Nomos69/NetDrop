# PyInstaller build definition. Run it from the repository root on Windows.
from pathlib import Path

project = Path(SPECPATH).parent.parent

a = Analysis(
    [str(project / 'app' / 'local_companion.py')],
    pathex=[str(project)],
    binaries=[],
    datas=[(str(project / 'static'), 'static')],
    hiddenimports=[
        'uvicorn.logging', 'uvicorn.loops.auto', 'uvicorn.protocols.http.auto',
        'uvicorn.protocols.websockets.auto', 'zeroconf',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [], exclude_binaries=True, name='NetDropLocal',
    debug=False, bootloader_ignore_signals=False, strip=False, upx=True,
    console=False,
)
coll = COLLECT(
    exe, a.binaries, a.datas, strip=False, upx=True, upx_exclude=[],
    name='NetDropLocal',
)
