.PHONY: build test lint deploy clean

PYTHON := .venv/bin/python
PYTEST := .venv/bin/pytest
RUFF := .venv/bin/ruff

build:
	$(PYTHON) build.py

test:
	$(PYTEST) tests/ -v

lint:
	$(RUFF) check lib/ tests/ build.py
	$(RUFF) format --check lib/ tests/ build.py

format:
	$(RUFF) format lib/ tests/ build.py

deploy: build
	@if git diff --quiet index.html kanban.html data.json; then \
	  echo "no public changes — skipping commit"; \
	else \
	  git add index.html kanban.html data.json && \
	  git commit -m "snapshot $$(date -u +%Y-%m-%dT%H:%M:%SZ)" && \
	  git push; \
	fi

clean:
	rm -rf __pycache__ .pytest_cache .ruff_cache
	find . -name "*.pyc" -delete
