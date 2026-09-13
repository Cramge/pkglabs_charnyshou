"""Test, build and record checksums. Run with the project virtualenv Python."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
SOURCES = ('main.py','controller.py','color_models.py','test_colors.py',
           'test_extended.py','test_ui.py','ColorLab.spec','build.py',
           'requirements.txt','requirements-build.txt','README.md','REPORT.md')

def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    subprocess.run([sys.executable,'-B','-m','unittest','-v','test_colors','test_extended','test_ui'],cwd=ROOT,check=True)
    subprocess.run([sys.executable,'-m','PyInstaller','--noconfirm','--clean',
                    '--distpath',str(ROOT),'--workpath',str(ROOT/'build'/'current'),
                    str(ROOT/'ColorLab.spec')],cwd=ROOT,check=True)
    import importlib.metadata
    info = {'built_at_utc':datetime.now(timezone.utc).isoformat(),
            'python':sys.version,'tests':'36 tests passed',
            'dependencies':{name:importlib.metadata.version(name) for name in ('customtkinter','Pillow','pyinstaller')},
            'sha256':{name:sha256(ROOT/name) for name in (*SOURCES,'ColorLab.exe')}}
    (ROOT/'BUILD_INFO.json').write_text(json.dumps(info,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Built:',ROOT/'ColorLab.exe')

if __name__ == '__main__': main()
