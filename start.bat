@echo off
rem Set up and run Intelli-Oppo.
rem
rem There is no server here. This is a CLI that calls a remote API; the script
rem exists so a fresh clone is one command away from working rather than six.
rem
rem   start.bat              argue with it
rem   start.bat demo         watch a scripted debate
rem   start.bat check        verify setup and reach the API
rem   start.bat test         run the offline test suite
rem   start.bat ask "..."    one turn, then exit
rem   start.bat setup        bootstrap only, run nothing

setlocal enabledelayedexpansion
cd /d "%~dp0"

set "VENV=.venv"
set "PY=%VENV%\Scripts\python.exe"

rem -- venv -------------------------------------------------------------
if not exist "%PY%" (
    call :find_python
    if errorlevel 1 (
        echo.
        echo   error: need Python 3.11 or newer on PATH ^(3.12 recommended^).
        echo   onnxruntime requires 3.11+, so older versions cannot work.
        echo   https://www.python.org/downloads/
        echo.
        exit /b 1
    )
    echo   creating virtual environment with !BASE_PY!
    !BASE_PY! -m venv "%VENV%"
    if errorlevel 1 (
        echo   error: could not create the virtual environment
        exit /b 1
    )
)

rem -- dependencies -----------------------------------------------------
"%PY%" -c "import intelli_oppo" >nul 2>&1
if errorlevel 1 (
    echo   installing dependencies ^(first run only^)
    "%PY%" -m pip install --quiet --upgrade pip
    "%PY%" -m pip install --quiet -e ".[dev]"
    if errorlevel 1 (
        echo   error: dependency installation failed
        exit /b 1
    )
)

rem -- key --------------------------------------------------------------
if not exist ".env" (
    copy ".env.example" ".env" >nul
    echo.
    echo   created .env - add your Groq key, then run this again
    echo   free key: https://console.groq.com/keys
    echo.
    exit /b 1
)

findstr /r /c:"^GROQ_TOKEN=..*" ".env" >nul 2>&1
if errorlevel 1 (
    echo.
    echo   .env has no GROQ_TOKEN - add one, then run this again
    echo   free key: https://console.groq.com/keys
    echo.
    exit /b 1
)

rem -- run --------------------------------------------------------------
set "MODE=%~1"
if "%MODE%"=="" set "MODE=run"
if not "%MODE%"=="" shift

if /i "%MODE%"=="run"   goto :run
if /i "%MODE%"=="demo"  goto :demo
if /i "%MODE%"=="check" goto :check
if /i "%MODE%"=="ask"   goto :ask
if /i "%MODE%"=="test"  goto :test
if /i "%MODE%"=="setup" goto :setup

echo   error: unknown mode '%MODE%'. Use: run, demo, check, ask, test, setup
exit /b 1

:run
"%PY%" -m intelli_oppo %1 %2 %3
exit /b %errorlevel%

:demo
"%PY%" -m intelli_oppo --demo
exit /b %errorlevel%

:check
"%PY%" -m intelli_oppo --check
exit /b %errorlevel%

:ask
"%PY%" -m intelli_oppo --ask %1
exit /b %errorlevel%

:test
"%PY%" -m pytest -q %1 %2 %3
exit /b %errorlevel%

:setup
echo   ready - start.bat demo to see it work
exit /b 0

rem -- helpers ----------------------------------------------------------
:find_python
for %%C in ("py -3.12" "py -3.13" "py -3.11" "python3.12" "python") do (
    for /f "delims=" %%V in ('%%~C -c "import sys; print(1 if sys.version_info[:2]>=(3,11) else 0)" 2^>nul') do (
        if "%%V"=="1" (
            set "BASE_PY=%%~C"
            exit /b 0
        )
    )
)
exit /b 1
