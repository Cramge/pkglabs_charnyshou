from pathlib import Path

import PyInstaller.__main__


root = Path(__file__).resolve().parent
PyInstaller.__main__.run(
    [
        str(root / "ImageHeaderLab.spec"),
        "--distpath",
        str(root / "dist"),
        "--workpath",
        str(root / "build"),
        "--noconfirm",
        "--clean",
    ]
)

