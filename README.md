# InstrumentalSW AI Module

Reproducible Python/FastAPI foundation for the InstrumentalSW project (Saxo). This iteration provides only the starter contracts and in-memory behavior required by **SAX-000**.

## Requirements

- Python `>=3.11,<3.14`
- `pip`

## Install

All runtime and development dependencies are installed with one command:

```bash
python -m pip install -e ".[dev]"
```

### Unix (bash/zsh)

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

### Windows (PowerShell)

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

Python 3.12 or 3.13 can be selected instead when installed.

## Run locally

```bash
python -m uvicorn saxo_ai.main:app --reload
```

PowerShell uses the same command. The service is available at `http://127.0.0.1:8000`; the OpenAPI UI is at `/docs`.

## Minimal API

- `GET /health`
- `POST /api/v1/transcriptions`
- `GET /api/v1/transcriptions/{job_id}`

The POST endpoint accepts multipart fields:

- `file`: non-empty `.mp3` or `.wav` file;
- `saxophone_type`: `soprano`, `alto`, `tenor`, or `baritone`;
- `input_mode`: `solo` or `mixture`.

Jobs are stored only in memory and begin with status `UPLOADED`.

## Quality commands

```bash
python -m pytest
python -m pytest --cov=saxo_ai --cov-report=term-missing
python -m ruff check src tests
python -m mypy
```

On Unix systems with `make`, `make check` runs the full local quality gate.

## Architecture

```text
src/saxo_ai/
├── api/             # FastAPI routes and transport schemas
├── application/     # Use cases and repository ports
├── domain/          # Domain models and transposition rules
├── infrastructure/  # In-memory repository adapter
└── main.py          # Application composition root
```

Dependencies point inward: API and infrastructure depend on application/domain contracts; the domain has no FastAPI or storage dependency.

## Scope boundaries

This starter does **not** decode or process audio, invoke FFmpeg, hash content, download models, run inference, train models, persist jobs, or use cloud services. Those capabilities belong to later stories.

Tests use only synthetic byte strings generated in code. Real audio, datasets, models, checkpoints, caches, virtual environments, local secrets, and generated artifacts are excluded by `.gitignore`.
