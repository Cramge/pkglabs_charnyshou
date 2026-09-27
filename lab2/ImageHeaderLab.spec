a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        "PIL.ImageTk",
        "PIL.BmpImagePlugin",
        "PIL.GifImagePlugin",
        "PIL.JpegImagePlugin",
        "PIL.PcxImagePlugin",
        "PIL.PngImagePlugin",
        "PIL.TiffImagePlugin",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=["pyi_rth_tk_paths.py"],
    excludes=[],
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
    name="ImageHeaderLab",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
)

