# Health Risk Portal Prototype

A Django application for personal health records, risk screening, population alerts, printable reports, and model training.

Screening and education only. Results are not medical diagnoses and must not replace professional care.

## Features

### For users

* Bilingual interface with one-click language switching.

<img width="2550" height="1233" alt="user-overview" src="https://github.com/user-attachments/assets/5ea14665-b1a5-40d0-a11a-b65af42d77b3" /><br>

* Record baseline measurements, blood pressure, mood, and sleep.

<img width="2550" height="1233" alt="user-health-records" src="https://github.com/user-attachments/assets/67f33270-399b-40ad-b16b-2b3c1bc0c33d" /><br>

* Query records and questionnaire detail views.

<img width="2550" height="1197" alt="user-health-data-entry" src="https://github.com/user-attachments/assets/dd0a9e1d-95e7-4c7e-a1ac-4b5c7652c90b" /><br>

* Personal risk panel: blood-pressure category, model-based hypertension/depression result, latest observation.

<img width="2550" height="1233" alt="user-health-alert" src="https://github.com/user-attachments/assets/97a6e65e-b85b-4746-a696-b0401b178e0c" /><br>

* Download an A4 PDF health report.  
<figure class="half">
  <img width="476" height="673" alt="health-report_1" src="https://github.com/user-attachments/assets/78dac306-936e-4d63-8d74-0e5a12e30cc9" />
  <img width="476" height="673" alt="health-report_2" src="https://github.com/user-attachments/assets/9d316241-44e0-4388-a86e-4a9b6daf1895" />
</figure>


### For administrators

* Population risk dashboard by year with distribution summaries and pie charts.

<img width="2550" height="1233" alt="admin-health-alert" src="https://github.com/user-attachments/assets/a9ba1121-97d0-4496-a964-6198e4427133" /><br>

* Generate a single PDF report or a ZIP containing up to 50 user reports.

<img width="2550" height="1233" alt="admin-health-report" src="https://github.com/user-attachments/assets/c534da07-d119-46e2-b69a-f3245f02e68a" /><br>

* Train and version models: Random Forest (hypertension), XGBoost (depression), and PCA (health components); optional five-fold validation; live training progress.

<img width="2550" height="1233" alt="admin-model-training" src="https://github.com/user-attachments/assets/e49b5f5d-fafc-4119-9927-13e45bbbe8b5" /><br>

* Select the latest model, a specific version, or disable a model.
* Create and disable accounts, reset passwords, configure session duration.
* Review and export activity logs as CSV.


## Quick Start (Windows)

1. Install **64-bit Python 3.10**.
2. Clone this repo or download and extract the ZIP. Open the directory containing `manage.py`, `requirements.txt` and `start-site.cmd`.
3. Double-click `start-site.cmd`. The first installation needs internet access and can take several minutes.
4. Open the printed address (e.g. `127.0.0.1:8000`). Keep the terminal open; press Ctrl+C to stop.

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


## Tech Stack

Python 3.10, Django 4.0, scikit-learn, XGBoost, pandas, NumPy, joblib, ReportLab, openpyxl, tzlocal, Chart.js, SQLite.


## Data and privacy

All data in this project is demonstration data. It contains no real user information and involves no real user privacy.

