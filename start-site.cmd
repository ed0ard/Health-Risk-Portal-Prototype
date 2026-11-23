@echo off
setlocal
rem Resolve everything relative to this file, including paths with spaces.
pushd "%~dp0" || exit /b 1
set "PYTHONDONTWRITEBYTECODE=1"
set "PYTHONUTF8=1"
set "PIP_DISABLE_PIP_VERSION_CHECK=1"
set "PIP_NO_INPUT=1"
set "PY="
if exist ".venv\Scripts\python.exe" set "PY=%CD%\.venv\Scripts\python.exe"
if defined PY goto validate
if defined HEALTH_PYTHON goto custom_python
py -3.10 -c "import sys; assert sys.version_info[:2] == (3, 10)" >nul 2>&1
if not errorlevel 1 (
    py -3.10 -m venv .venv
    if errorlevel 1 goto failed
    goto created
)
python -c "import sys; assert sys.version_info[:2] == (3, 10)" >nul 2>&1
if errorlevel 1 goto missing_python
python -m venv .venv
if errorlevel 1 goto failed
goto created

:custom_python
"%HEALTH_PYTHON%" -c "import sys; assert sys.version_info[:2] == (3, 10)" >nul 2>&1
if errorlevel 1 goto missing_python
"%HEALTH_PYTHON%" -m venv .venv
if errorlevel 1 goto failed

:created
set "PY=%CD%\.venv\Scripts\python.exe"
goto install

:validate
"%PY%" -c "import sys; assert sys.version_info[:2] == (3, 10)" >nul 2>&1
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
echo Install Python 3.10, or set HEALTH_PYTHON to its python.exe path.
echo If a local .venv was moved or uses another Python version, recreate it.
goto failed

:failed
echo Startup failed. See the error above.
popd
exit /b 1
