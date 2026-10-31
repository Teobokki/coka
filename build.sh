#!/bin/bash
# Windows build via Wine: PyInstaller onedir + Inno Setup per-user installer + onefile portable + zip
set -e
export WINEPREFIX=/workspace/exwifi/.wine WINEDEBUG=-all
cd "$(dirname "$0")"
V=$(grep -oP '^VERSION = "\K[^"]+' coka.py)
PY='C:\Python311\python.exe'
wine "$PY" -m PyInstaller --noconfirm "COKA.spec" > build_dir.log 2>&1; echo DIR_DONE
wine "C:\\InnoSetup\\ISCC.exe" installer.iss > build_iss.log 2>&1; echo ISS_DONE
wine "$PY" -m PyInstaller --noconfirm --workpath build_onefile --distpath dist_onefile "COKA onefile.spec" > build_1f.log 2>&1
cp "dist_onefile/COKA.exe" dist/COKA-Portable.exe; echo ONEFILE_DONE
cd dist && rm -f COKA-$V-Windows-x64.zip && python3 -c "import shutil; shutil.make_archive('COKA-$V-Windows-x64', 'zip', '.', 'COKA')" && echo ZIP_DONE
ls -la
