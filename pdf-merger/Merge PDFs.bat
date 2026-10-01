@echo off
title Merge PDFs
cd /d "%~dp0"

rem Find Python ("py" launcher first, then "python")
set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY where python >nul 2>nul && set "PY=python"
if not defined PY (
    echo Python is not installed.
    echo Install it from https://www.python.org/downloads/  ^(tick "Add python.exe to PATH"^)
    pause
    exit /b 1
)

rem Install pypdf the first time only
%PY% -c "import pypdf" >nul 2>nul || (
    echo Installing pypdf ^(one time only^)...
    %PY% -m pip install --user --quiet pypdf
)

rem %1 = folder dragged onto this file (optional)
%PY% "%~dp0merge_pdfs.py" %1
if errorlevel 1 pause
