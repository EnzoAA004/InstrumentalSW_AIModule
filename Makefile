.PHONY: install test coverage lint type check run

install:
	python -m pip install -e ".[dev]"

test:
	python -m pytest

coverage:
	python -m pytest --cov=saxo_ai --cov-report=term-missing

lint:
	python -m ruff check src tests

type:
	python -m mypy

check: test coverage lint type

run:
	python -m uvicorn saxo_ai.main:app --reload
