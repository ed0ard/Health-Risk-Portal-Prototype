# Health Risk Portal Prototype

A bilingual Django application for personal health records, risk screening, population alerts, printable reports, and model training.

Screening and education only. Results are not medical diagnoses and must not replace professional care.

## Features

### For users

* Bilingual interface with one-click language switching.
* Record baseline measurements, blood pressure, mood (9 items), and sleep (7 items).
* Query records and questionnaire detail views.
* Personal risk panel: blood-pressure category, model-based hypertension/depression result, latest observation.
* Download an A4 PDF health report.

### For administrators

* Population risk dashboard by year with distribution summaries and pie charts.
* Generate a single PDF report or a ZIP containing up to 50 member reports.
* Train and version models: Random Forest (hypertension), XGBoost (depression), and PCA (health components); optional five-fold validation; live training progress.
* Select the latest model, a specific version, or disable a model.
* Create and disable accounts, reset passwords, configure session duration.
* Review and export activity logs as CSV.

## Tech Stack

Python 3.10, Django 4.0, scikit-learn, XGBoost, pandas, NumPy, joblib, ReportLab, openpyxl, tzlocal, Chart.js, SQLite.

## Quick Start (Windows)

1. Install **64-bit Python 3.10**.
2. Clone the repository or download and extract its ZIP. Open the directory containing `manage.py`, `requirements.txt` and `start-site.cmd`.
3. Double-click `start-site.cmd`. The first installation needs internet access and can take several minutes.
4. Open the printed address. Keep the terminal open; press Ctrl+C to stop.

If Python 3.10 is installed but the launcher cannot find it, set its full executable path in PowerShell. For example:

```powershell
$env:HEALTH_PYTHON = 'C:\Path\To\Python310\python.exe'
./start-site.cmd
```


### Demo accounts

|Username|Role|Initial password|
|-|-|-|
|`admin`|Administrator|`Password123!`|
|`1`|User|`Password123!`|


## Project Layout

```text
manage.py
config/        Django settings and URL routing
portal/        models, views, templates, static assets, tests
training/      standalone data loader and model trainer
data/source/   demonstration workbooks, accounts and pretrained models
data/models/   trained model files referenced by the demo database
db.sqlite3     demonstration accounts, records and model history
start-site.cmd Windows launcher
```


## Data and privacy

All data in this project is demonstration data. It contains no real user information and involves no real user privacy.
