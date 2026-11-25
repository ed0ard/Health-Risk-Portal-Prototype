<div align="center">

# Health Risk Portal Prototype

[Quick start](#quick-start-windows) · [Features](#features) · [UML diagrams](https://ed0ard.github.io/Health-Risk-Portal-Prototype/) · [Project Layout](#project-layout)

</div>

A Django web application for public health screening and health data management with an integrated assistant, Doc Pup.

Screening and education only. Results are not medical diagnoses and must not replace professional care.


## Features

### Doc Pup

* Drop Doc Pup on a text block to read aloud from here onward.
* Voice input to fill in the form.

https://github.com/user-attachments/assets/41a78990-2932-48f5-be8a-4dc2927daf93

* Drop an audio, PDF, TXT or DOCX file to fill out the form.

https://github.com/user-attachments/assets/f5aaac1f-25d6-49c9-9e68-19ce0ca9a8cf

* Left-Click for summaries and health suggestions for individuals, or briefings for administrators.

https://github.com/user-attachments/assets/794790b2-e096-4448-95ee-f9e7ea94329d

* Local `Spark-X2.6-4B (Q8_0, GGUF)` for generation; local `Whisper-small` for automatic speech recognition; `Edge TTS` for text-to-speech with a local `pyttsx3` fallback.

### User Features

* Switch between English and Chinese with one click.

<img width="2522" height="1267" alt="user-overview" src="https://github.com/user-attachments/assets/59e62f0d-3c2c-4f13-9023-2a145012e1a8" /><br>

* Record baseline measurements, blood pressure, mood, and sleep.

<img width="2538" height="1266" alt="user-health-records" src="https://github.com/user-attachments/assets/c143918e-acfc-4de8-9ae0-f5606269d5c7" /><br>

* Browse health records and view questionnaire responses.

<img width="2521" height="1271" alt="user-health-data-entry" src="https://github.com/user-attachments/assets/7d4ed0c2-8ca8-44ee-910c-2dc532c26919" /><br>

* View personal risk assessments, blood pressure categories, and recent observations.

<img width="2525" height="1272" alt="user-health-alert" src="https://github.com/user-attachments/assets/f70b7d76-f1c1-4f9e-89cb-2e03f6ae6019" /><br>

* Download an A4 PDF health report.  

<img width="1096" height="788" alt="health-report" src="https://github.com/user-attachments/assets/a57d84d4-5235-4372-b0f6-ff2611a0d9ec" />


### Administrator Features

* View annual population risk summaries and distribution charts.

<img width="2521" height="1268" alt="admin-health-alert" src="https://github.com/user-attachments/assets/6e333c5f-747a-42e9-9ecd-c44b0fbfd56e" /><br>

* Generate a single PDF report or export up to 50 user reports as a ZIP.

<img width="2522" height="1271" alt="admin-health-report" src="https://github.com/user-attachments/assets/7ca463a6-e6cd-4627-a4ab-a605227a84fe" /><br>

* Train and manage Random Forest (hypertension), XGBoost (depression), and PCA (health components) models, with optional five-fold validation and live training progress.

<img width="2507" height="1270" alt="admin-model-training" src="https://github.com/user-attachments/assets/886d2002-f821-406b-af9d-f7604ab39aa0" /><br>

* Create accounts, disable access, and reset passwords.
* Configure model selection for each assessment, Doc Pup controls, session and login security.

<img width="1602" height="1272" alt="admin-settings" src="https://github.com/user-attachments/assets/d3e63dbb-6fe4-4aed-875f-81682733be9a" /><br>

* Review activity logs and export them as CSV.


## Quick Start (Windows)

1. Clone this repo or download and extract the ZIP.

2. Double-click `start-site.cmd`. It creates `.venv`, installs the complete `requirements.txt`, initializes SQLite and demo data, downloads the required Doc Pup models and runtime, and starts the server.

3. Open address printed in the terminal (e.g. `127.0.0.1:8000`). Keep the terminal open; Ctrl+C stops the web server.

The first run needs about 15 GB of free disk space; a machine with 8 GB of VRAM and 16 GB of RAM is recommended.

To use a specific existing Python 3.10 installation, optionally set its full executable path in PowerShell. For example:

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
config/                 Django settings, URL routing, ASGI and WSGI entry points
portal/                 records, accounts, risk assessment, reports and Doc Pup
portal/templates/       bilingual Django page templates
portal/static/          styles, JavaScript, Doc Pup assets and bundled Chart.js
portal/management/      setup, model import, server and assistant check commands
portal/migrations/      database schema migrations
training/               workbook data loader and original model trainer
scripts/                source release packaging
docs/                   UML diagrams and sources
data/source/            demonstration workbooks, accounts and supplied models
data/models/            trained model artifacts referenced by Fit records
data/docpup/            downloaded language/speech models and tokenizer cache
requirements.txt        application and Doc Pup dependencies
start-site.cmd          Windows setup and startup launcher
```


## Tech Stack

> **Runtime** · Python **3.10** · Django **4.0.4** · SQLite · Windows **x64**
>
> **Interface** · Django templates · vanilla JavaScript / CSS · bundled Chart.js **4.4.9**
>
> **Data & ML** · NumPy **1.26.4** · pandas **2.x** · scikit-learn **1.6.1** · XGBoost **3.0.1** · joblib **1.4–<2**
>
> **Reports & import** · ReportLab **4.x** · openpyxl **3.1–<4** · pypdf **5–<8** · python-docx **1.1–<2**
>
> **Local AI** · Ollama · Spark-X2.6-4B **Q8_0 GGUF** · faster-whisper **1.2.1** / Whisper-small · PyAV **16.1.0**
>
> **Voice & integration** · Edge TTS **7.2–<8** · pyttsx3 **2.99** · Hugging Face Hub · tokenizers · requests · psutil


## Data and privacy

All data in this project is demonstration data.

It contains no real user information and involves no real user privacy.

Health records are stored in a local SQLite database.
