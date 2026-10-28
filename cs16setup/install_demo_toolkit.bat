@echo off
rem ============================================================
rem  cs16db Demo Toolkit installer for CS 1.6
rem  Installs: MetaMod-p + AMX Mod X (platform for plugins),
rem  movie.cfg (record/camera/slow-mo/bot scene kit) and
rem  autoexec.cfg wiring - into every CS 1.6 install found.
rem
rem  Usage: install_demo_toolkit.bat [game_dir ...]
rem  (no args = auto-detect the two known installs)
rem ============================================================
setlocal EnableExtensions
set ROOT=%~dp0
set DOWN=%ROOT%downloads
set STAGE=%ROOT%staging

rem ---------- known installs (edit if needed) ----------
set "GAME1=D:\Counter-Strike Build 4554"
set "GAME2=D:\CS 1.6 GoldClient"

set "MM_URL=https://github.com/Bots-United/metamod-p/releases/download/v1.21p109/metamod-p-v1.21p109-win32.tar.xz"
set "MM_FILE=metamod.tar.xz"
set "AMXX_URL=https://github.com/alliedmodders/amxmodx/releases/download/1.10.0.5487/amxmodx-1.10.0-git5487-base-windows.zip"
set "AMXX_BASE=amxx_base.zip"
set "AMXX_CS_URL=https://github.com/alliedmodders/amxmodx/releases/download/1.10.0.5487/amxmodx-1.10.0-git5487-cstrike-windows.zip"
set "AMXX_CS=amxx_cs.zip"

mkdir "%DOWN%" 2>nul
mkdir "%STAGE%" 2>nul

echo === [0/4] download components (skip if already present) ===
if not exist "%DOWN%\%MM_FILE%" (
    curl.exe -L -s -o "%DOWN%\%MM_FILE%" "%MM_URL%" || (echo [error] metamod download failed & exit /b 1)
)
if not exist "%DOWN%\%AMXX_BASE%" (
    curl.exe -L -s -o "%DOWN%\%AMXX_BASE%" "%AMXX_URL%" || (echo [error] amxx base download failed & exit /b 1)
)
if not exist "%DOWN%\%AMXX_CS%" (
    curl.exe -L -s -o "%DOWN%\%AMXX_CS%" "%AMXX_CS_URL%" || (echo [error] amxx cstrike download failed & exit /b 1)
)

echo === [1/4] unpack to staging (fresh) ===
if exist "%STAGE%\mm" rd /s /q "%STAGE%\mm"
if exist "%STAGE%\ab" rd /s /q "%STAGE%\ab"
if exist "%STAGE%\acs" rd /s /q "%STAGE%\acs"
python -c "import lzma,tarfile,os; src=r'%DOWN%\%MM_FILE%'; dst=r'%STAGE%\mm'; os.makedirs(dst,exist_ok=True); f=lzma.open(src); t=tarfile.open(fileobj=f); t.extractall(dst); print('metamod unpacked')" || (echo [error] metamod unpack failed & exit /b 1)
powershell -NoProfile -Command "Expand-Archive -Path '%DOWN%\%AMXX_BASE%' -DestinationPath '%STAGE%\ab' -Force" || (echo [error] amxx base unpack failed & exit /b 1)
powershell -NoProfile -Command "Expand-Archive -Path '%DOWN%\%AMXX_CS%' -DestinationPath '%STAGE%\acs' -Force" || (echo [error] amxx cs unpack failed & exit /b 1)
if not exist "%STAGE%\mm\addons\metamod\dlls\metamod.dll" (echo [error] staging incomplete - rerun & exit /b 1)

rem ---------- game dirs ----------
set "G1=D:\Counter-Strike Build 4554"
set "G2=D:\CS 1.6 GoldClient"
if not "%~1"=="" set "G1=%~1"
if not "%~2"=="" set "G2=%~2"
for %%G in ("%G1%" "%G2%") do call :install_game %%G
goto :done

:install_game
set "GAME=%~1"
if not exist "%GAME%\cstrike" (echo [skip] %GAME% - no cstrike folder & goto :eof)
echo.
echo === [2/4] install into %GAME% ===
set "CR=%GAME%\cstrike"
for /f "tokens=1-3 delims=/ " %%a in ("%DATE%") do set "TS=%%c%%b%%a"
for /f "tokens=1-2 delims=: " %%a in ("%TIME%") do set "TS=%TS%_%%a%%b"
if "%TS%"=="" set TS=backup

rem backup what we touch
if exist "%CR%\addons" xcopy /e /i /y /q "%CR%\addons" "%CR%\addons_backup_%TS%" >nul 2>&1
if exist "%CR%\liblist.gam" copy /y "%CR%\liblist.gam" "%CR%\liblist.gam.bak" >nul 2>&1
if exist "%CR%\autoexec.cfg" copy /y "%CR%\autoexec.cfg" "%CR%\autoexec.cfg.bak" >nul 2>&1

rem metamod + amxmodx files
xcopy /e /i /y /q "%STAGE%\mm\addons\metamod" "%CR%\addons\metamod" >nul 2>&1
xcopy /e /i /y /q "%STAGE%\ab\addons\amxmodx" "%CR%\addons\amxmodx" >nul 2>&1
xcopy /e /i /y /q "%STAGE%\acs\addons\amxmodx" "%CR%\addons\amxmodx" >nul 2>&1

rem ---- metamod config.ini: unquoted paths, forward slashes (metamod-p parser!) ----
if exist "%CR%\dlls\csbot.dll" (
    echo gamedll dlls/csbot.dll> "%CR%\addons\metamod\config.ini"
) else (
    echo gamedll dlls/mp.dll> "%CR%\addons\metamod\config.ini"
)
echo gamedll_linux dlls/cs_i386.so>> "%CR%\addons\metamod\config.ini"

rem ---- metamod plugins.ini: load amxmodx ----
if not exist "%CR%\addons\metamod\plugins.ini" (
    echo win32 addons/amxmodx/dlls/amxmodx_mm.dll> "%CR%\addons\metamod\plugins.ini"
    echo linux addons/amxmodx/dlls/amxmodx_mm_i386.so>> "%CR%\addons\metamod\plugins.ini"
) else (
    findstr /C:"amxmodx_mm.dll" "%CR%\addons\metamod\plugins.ini" >nul 2>&1 || echo win32 addons/amxmodx/dlls/amxmodx_mm.dll>> "%CR%\addons\metamod\plugins.ini"
)

rem ---- liblist.gam: point gamedll at metamod ----
powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%patch_liblist.ps1" -Path "%CR%\liblist.gam" || (echo [error] liblist.gam patch failed & goto :eof)

rem ---- demo_toolkit plugin (record names, edit log, spots) ----
if exist "%ROOT%plugin\demo_toolkit.amxx" (
    copy /y "%ROOT%plugin\demo_toolkit.amxx" "%CR%\addons\amxmodx\plugins\demo_toolkit.amxx" >nul 2>&1
    findstr /C:"demo_toolkit.amxx" "%CR%\addons\amxmodx\configs\plugins.ini" >nul 2>&1 || echo demo_toolkit.amxx>> "%CR%\addons\amxmodx\configs\plugins.ini"
    if exist "%ROOT%plugin\demo_toolkit.sma" copy /y "%ROOT%plugin\demo_toolkit.sma" "%CR%\addons\amxmodx\scripting\demo_toolkit.sma" >nul 2>&1
    echo [ok] demo_toolkit.amxx installed
) else (
    echo [warn] plugin\demo_toolkit.amxx missing - build with plugin\build_plugin.bat
)

rem ---- movie.cfg + autoexec wiring ----
copy /y "%ROOT%movie.cfg" "%CR%\movie.cfg" >nul 2>&1
if not exist "%CR%\autoexec.cfg" (
    echo exec movie.cfg> "%CR%\autoexec.cfg"
) else (
    findstr /C:"movie.cfg" "%CR%\autoexec.cfg" >nul 2>&1 || echo exec movie.cfg>> "%CR%\autoexec.cfg"
)

echo [ok] %GAME%: metamod + amxmodx + movie.cfg installed
goto :eof

:done
echo.
echo === [3/4] done ===
echo   Plugins: cstrike\addons\metamod + addons\amxmodx ^(AMX Mod X^)
echo   Plugin:  addons\amxmodx\plugins\demo_toolkit.amxx ^(F6/F7, /rec, /stop, events^)
echo   Kit:     cstrike\movie.cfg ^(F4-F11, see file header^)
echo   Wire:    autoexec.cfg exec movie.cfg
echo   Backups: addons_backup_*, liblist.gam.bak, autoexec.cfg.bak
echo   Verify:  start CS 1.6, console: meta list / amxx version
echo   Restore: cs16setup\restore_backup.bat
echo === [4/4] sanity: metamod.dll in both installs ===
for %%G in ("%G1%" "%G2%") do call :check_game %%G
endlocal
goto :eof

:check_game
if exist "%~1\cstrike\addons\metamod\dlls\metamod.dll" (echo   [ok] %~1) else (echo   [MISSING] %~1)
goto :eof
