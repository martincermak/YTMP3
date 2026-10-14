@echo off
setlocal
REM 1) stahne zavislosti do deps\   2) sestavi dist\YTMP3.exe
REM 3) pokud je Inno Setup, sestavi installer\YTMP3-Setup.exe (se vsemi zavislostmi uvnitr)

python -m pip install -r requirements.txt
if errorlevel 1 goto :err
python fetch_deps.py
if errorlevel 1 goto :err
python -m PyInstaller --onefile --noconsole --name YTMP3 --collect-all customtkinter --hidden-import PIL._tkinter_finder app.py
if errorlevel 1 goto :err

set "ISCC="
where iscc >nul 2>&1 && set "ISCC=iscc"
if not defined ISCC if exist "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if not defined ISCC if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not defined ISCC if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"

if not defined ISCC goto :noinno
"%ISCC%" installer.iss
if errorlevel 1 goto :err
echo.
echo Hotovo: installer\YTMP3-Setup.exe
echo Test: nainstaluj a spust  python tests\e2e_test.py
goto :end

:noinno
echo.
echo Hotovo: dist\YTMP3.exe
echo Inno Setup nenalezen - instalator se nesestavil.
echo Nainstaluj ho: winget install JRSoftware.InnoSetup  a spust build.bat znovu.
goto :end

:err
echo.
echo CHYBA pri sestaveni.

:end
pause
