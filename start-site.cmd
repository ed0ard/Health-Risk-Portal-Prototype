@echo off
setlocal
rem Resolve everything relative to this file, including paths with spaces.
pushd "%~dp0" || goto failed_no_directory
set "PYTHONDONTWRITEBYTECODE=1"
set "PYTHONUTF8=1"
rem Do not inherit another Python installation's standard library or import paths.
set "PYTHONHOME="
set "PYTHONPATH="
set "UV_INTERNAL__PYTHONHOME="
set "PIP_DISABLE_PIP_VERSION_CHECK=1"
set "PIP_NO_INPUT=1"
set "PY="
if exist ".venv\Scripts\python.exe" set "PY=%CD%\.venv\Scripts\python.exe"
if defined PY goto validate
if exist ".venv\" goto missing_python
if defined HEALTH_PYTHON goto custom_python
if exist ".runtime\python-3.10.20\python.exe" goto local_python
py -3.10 -c "import sys, struct; assert sys.version_info[:2] == (3, 10) and struct.calcsize('P') == 8" >nul 2>&1
if not errorlevel 1 (
    py -3.10 -m venv .venv
    if errorlevel 1 goto failed
    goto created
)
python -c "import sys, struct; assert sys.version_info[:2] == (3, 10) and struct.calcsize('P') == 8" >nul 2>&1
if errorlevel 1 goto local_python
python -m venv .venv
if errorlevel 1 goto failed
goto created

:custom_python
"%HEALTH_PYTHON%" -c "import sys, struct; assert sys.version_info[:2] == (3, 10) and struct.calcsize('P') == 8" >nul 2>&1
if errorlevel 1 goto missing_python
"%HEALTH_PYTHON%" -m venv .venv
if errorlevel 1 goto failed
goto created

:local_python
echo Preparing project-local Python 3.10.20...
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\bootstrap-python.ps1"
if errorlevel 1 goto failed

:created
set "PY=%CD%\.venv\Scripts\python.exe"
goto install

:validate
"%PY%" -c "import sys, struct; assert sys.version_info[:2] == (3, 10) and struct.calcsize('P') == 8" >nul 2>&1
if errorlevel 1 goto missing_python
"%PY%" -c "import django, numpy, sklearn, xgboost, joblib, openpyxl, reportlab, pandas, tzlocal; from importlib.metadata import version; from packaging.requirements import Requirement; rs=[Requirement(s.strip()) for s in open('requirements.txt') if s.strip() and not s.startswith('#')]; assert all(version(r.name) in r.specifier for r in rs)" >nul 2>&1
if not errorlevel 1 goto ready

:install
"%PY%" -m ensurepip --upgrade
if errorlevel 1 goto failed
"%PY%" -m pip install -r requirements.txt
if errorlevel 1 goto failed

:ready
"%PY%" -m portal.bootstrap %*
if errorlevel 1 goto failed

:done
popd
exit /b 0

:missing_python
echo Python 3.10 is required for the pinned dependencies and supplied models.
echo Python 3.11-3.14 are not supported by this dependency set.
echo HEALTH_PYTHON must point to a working 64-bit Python 3.10, if set.
echo If .venv is broken or incompatible, rename it and run this launcher again.
echo With no .venv or HEALTH_PYTHON override, Python 3.10 is downloaded automatically if needed.
echo A newer system Python can coexist with the project's Python 3.10 environment.
goto failed

:failed
echo Startup failed. See the error above.
popd
:failed_no_directory
rem Keep double-click failures visible; automation can explicitly disable the pause.
if not "%HEALTH_NO_PAUSE%"=="1" pause
exit /b 1
