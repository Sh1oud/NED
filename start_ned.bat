@echo off
rem ===================================================================
rem  NED launcher for Windows
rem
rem  Double-click this file after extracting the ZIP. Flow:
rem    1. locate the project root (this file must sit next to pyproject.toml)
rem    2. find a working Python 3.12+ ("py -3" first, then "python")
rem    3. create a project-local .venv if it does not exist yet
rem    4. pip install -e .                       (first run, needs internet)
rem    5. settle the casebook startup mode. The reader picks normal mode or
rem       casebook mode unless NED_CASEBOOK was already set explicitly.
rem    6. start the CLI entry point from pyproject.toml: ned serve
rem
rem  NOTES -- please do not "fix" the following:
rem    * ASCII ONLY. A .bat file is read using the console codepage of the
rem      machine, which differs between locales. Non-ASCII bytes are therefore
rem      decoded as different characters on different PCs, and mis-decoded
rem      bytes can be split by cmd.exe and executed as unrelated commands.
rem      That is why this file contains no chcp call and no non-English text.
rem    * CRLF line endings are required: cmd.exe mis-parses LF-only batch
rem      files. .gitattributes marks *.bat as "-text" so the bytes stored in
rem      git -- and inside GitHub's "Download ZIP" -- stay CRLF.
rem    * The CLI is always started through its absolute path, never via PATH.
rem    * The casebook mode is set with "set" - this cmd.exe process only,
rem      inside the setlocal below - and never with "setx". NED must not
rem      change the Windows user or system environment, and the choice has
rem      to die with this window.
rem ===================================================================
setlocal EnableExtensions
title NED launcher

rem ---------- 0. must run from the project root ----------
cd /d "%~dp0"
if not exist "pyproject.toml" goto :err_not_project
if not exist "ned\app\cli.py" goto :err_not_project
echo.
echo [NED] Project folder: %CD%
echo [NED] Checking Python...

rem ---------- 1. find a Python 3.12+ that actually works ----------
rem "py -3 --version" has to print a version: py.exe can exist without a usable
rem Python 3, and "python" can be the Microsoft Store placeholder (no output).
set "NED_PY="
set "NED_VER="

for /f "tokens=1,2" %%A in ('py -3 --version 2^>nul') do set "NED_VER=%%A %%B"
if not defined NED_VER goto :try_python_cmd
echo %NED_VER%| findstr /b /c:"Python 3." >nul
if errorlevel 1 goto :try_python_cmd
set "NED_PY=py -3"
goto :python_found

:try_python_cmd
set "NED_VER="
for /f "tokens=1,2" %%A in ('python --version 2^>nul') do set "NED_VER=%%A %%B"
if not defined NED_VER goto :err_no_python
echo %NED_VER%| findstr /b /c:"Python 3." >nul
if errorlevel 1 goto :err_no_python
set "NED_PY=python"

:python_found
for /f "tokens=2" %%V in ("%NED_VER%") do set "NED_PY_VER=%%V"
for /f "tokens=1 delims=." %%X in ("%NED_PY_VER%") do set "NED_PY_MAJOR=%%X"
for /f "tokens=2 delims=." %%Y in ("%NED_PY_VER%") do set "NED_PY_MINOR=%%Y"
if not "%NED_PY_MAJOR%"=="3" goto :err_py_too_old
if %NED_PY_MINOR% LSS 12 goto :err_py_too_old
echo [NED] Found Python %NED_PY_VER% (launcher: %NED_PY%)

rem ---------- 2. project-local environment ----------
set "NED_VENV=%~dp0.venv"
set "NED_VPY=%NED_VENV%\Scripts\python.exe"
set "NED_CLI=%NED_VENV%\Scripts\ned.exe"

if not exist "%NED_VPY%" goto :install_package
"%NED_VPY%" -c "import ned" >nul 2>nul
if errorlevel 1 goto :install_package
if not exist "%NED_CLI%" goto :install_package
"%NED_CLI%" version >nul 2>nul
if errorlevel 1 goto :install_package
echo [NED] Local environment is ready, skipping install.
goto :startup_mode

:install_package
if exist "%NED_VPY%" goto :do_install
echo [NED] Preparing local environment (.venv, first run only)...
%NED_PY% -m venv "%NED_VENV%"
if not exist "%NED_VPY%" goto :err_venv_failed

:do_install
echo [NED] Installing NED (pip install -e ., needs internet)...
"%NED_VPY%" -m pip install --disable-pip-version-check -e "%~dp0."
if errorlevel 1 goto :err_install_failed
if not exist "%NED_CLI%" goto :err_launcher_missing

rem ---------- 3. casebook startup mode ----------
rem The casebook is opt-in and it is only about *keeping* material: mode 2
rem lets the reader file input into the local casebook, it never means
rem "analyse and save everything". A plain analysis stores nothing in
rem either mode. NED_CASEBOOK is set for this process only.
:startup_mode
set "NED_CASEBOOK_MODE="
set "NED_MODE_SOURCE=menu"
rem The product accepts a small vocabulary for this switch (see
rem ned/app/store/paths.py). Recognise the same words, so an explicit
rem setting is never silently overridden by the menu. An empty value
rem counts as "not configured" and the reader is asked.
for %%V in (on 1 true yes enable enabled) do if /i "%NED_CASEBOOK%"=="%%V" set "NED_CASEBOOK_MODE=on"
for %%V in (off 0 false no disable disabled) do if /i "%NED_CASEBOOK%"=="%%V" set "NED_CASEBOOK_MODE=off"
if defined NED_CASEBOOK_MODE set "NED_MODE_SOURCE=caller"
if defined NED_CASEBOOK_MODE goto :mode_summary

rem No explicit, legal NED_CASEBOOK: ask. The mode starts as "off" and
rem only the exact answer 2 turns it on, so a mistyped key, an empty
rem line, a closed input or an interrupt can never enable the casebook.
set "NED_CASEBOOK_MODE=off"
echo.
echo [NED] Startup mode
echo.
echo   [1] Normal mode
echo       Casebook off. Nothing is filed or kept.
echo.
echo   [2] Casebook on
echo       You may file material into a local casebook yourself.
echo       A plain analysis still saves nothing automatically.
echo.
set "NED_CHOICE="
set /p "NED_CHOICE=Choose [1/2]: "
if "%NED_CHOICE%"=="2" set "NED_CASEBOOK_MODE=on"
if not "%NED_CHOICE%"=="1" if not "%NED_CHOICE%"=="2" echo [NED] Not 1 or 2 - using normal mode.

:mode_summary
if "%NED_MODE_SOURCE%"=="caller" (
  echo [NED] Casebook: %NED_CASEBOOK_MODE% (from NED_CASEBOOK, set before startup)
) else if "%NED_CASEBOOK_MODE%"=="on" (
  echo [NED] Casebook: ON - you may file material into the local casebook yourself.
  echo [NED] A plain analysis still saves nothing automatically.
) else (
  echo [NED] Casebook: OFF - nothing is filed or kept.
)
set "NED_CASEBOOK=%NED_CASEBOOK_MODE%"

rem ---------- 4. start the local server ----------
:launch
echo.
echo [NED] Starting local server...
echo [NED] Open http://127.0.0.1:8000/ in your browser.
echo [NED] Keep this window open; press Ctrl+C to stop the server.
echo.
start "" /min cmd /c "timeout /t 4 /nobreak >nul & start http://127.0.0.1:8000/"
"%NED_CLI%" serve
set "NED_EXIT=%errorlevel%"
echo.
echo [NED] Server stopped (exit code %NED_EXIT%).
if not "%NED_EXIT%"=="0" echo [NED] Hint: retry with "%NED_VPY%" -m ned.app.cli serve
pause
exit /b %NED_EXIT%

rem ---------- error branches: every one of them pauses ----------
:err_not_project
echo.
echo [ERROR] NED project files were not found.
echo         Keep start_ned.bat in the same folder as pyproject.toml and
echo         extract the ZIP completely before running it.
pause
exit /b 1

:err_no_python
echo.
echo [ERROR] Python 3.12+ was not found.
echo         1. Install Python 3.12 or newer:
echo            https://www.python.org/downloads/windows/
echo            Tick "Add python.exe to PATH" while installing.
echo         2. If Python is installed but this error persists, the Microsoft
echo            Store app-execution alias may be in the way:
echo            Settings - Apps - Advanced app settings - App execution aliases,
echo            switch off python.exe and python3.exe, then run this file again.
pause
exit /b 1

:err_py_too_old
echo.
echo [ERROR] Python %NED_PY_VER% is too old; NED needs 3.12 or newer.
echo         Download: https://www.python.org/downloads/windows/
pause
exit /b 1

:err_venv_failed
echo.
echo [ERROR] Could not create the local environment (.venv).
echo         Common causes: no write permission, no free disk space, antivirus.
echo         If the ZIP was extracted into a protected folder such as
echo         C:\Program Files, extract it to Desktop or Documents instead.
echo         Manual retry: %NED_PY% -m venv "%~dp0.venv"
pause
exit /b 1

:err_install_failed
echo.
echo [ERROR] Installing NED failed (pip install -e . returned an error).
echo         Common causes: no internet access, corporate proxy, missing pip.
echo         Manual retry:
echo             cd /d "%~dp0"
echo             .venv\Scripts\python.exe -m pip install -e .
pause
exit /b 1

:err_launcher_missing
echo.
echo [ERROR] Install finished but .venv\Scripts\ned.exe is missing.
echo         Delete the .venv folder and run this file again.
pause
exit /b 1
