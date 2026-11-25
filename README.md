# NexusBridge — Academia–Industry Collaboration Portal

Production-grade Django 5.x portal connecting **Students**, **Universities**, and **Industry Partners** with standardized skill verification, explainable 0–100% Match Score recommendations, an end-to-end Application Tracking System (ATS), and Chart.js campus placement analytics.

## Tech Stack & Architecture
- **Backend:** Python 3.11+ / 3.12+, Django 5.x, Django ORM (SQLite dev default, PostgreSQL-ready via `dj-database-url`)
- **Frontend:** Django Templates + HTMX + Alpine.js + Tailwind CSS + Lucide Icons + Chart.js
- **Layered Architecture:** Thin views (`views.py`), business logic & state machines (`services/`), N+1-free queries & aggregations (`selectors/`), and constraint-enforced models (`models.py`)

## Quick Start

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
.venv\Scripts\python.exe manage.py migrate
.venv\Scripts\python.exe manage.py seed_data
.venv\Scripts\python.exe manage.py runserver
```

## Demo Accounts (Password: `DemoPass123!`)
- **Student:** `student@nitk.edu`
- **Company:** `hr@cloudscale.io`
- **University Admin:** `admin@nitk.edu`

## Running Verification & Tests

```powershell
.venv\Scripts\python.exe manage.py check
.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.venv\Scripts\pytest.exe
```
