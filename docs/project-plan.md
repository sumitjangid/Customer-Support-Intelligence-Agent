# Project Plan and Step-by-Step Guide

This document tracks the implementation in small milestones. Each milestone should leave the project runnable and tested before the next one begins.

## Product goal

Build an API that helps support agents understand, prioritize, and respond to customer tickets. It retrieves relevant internal knowledge, returns structured recommendations, and keeps a human responsible for customer-facing actions.

## Milestones

### 1. API foundation — complete

- Establish a Python package and FastAPI application.
- Add a health endpoint and an automated API test.
- Record the architecture and local development instructions.

**Done when:** the application starts locally and the health test passes.

### 2. Domain models and ticket intake — complete

- Define validated Pydantic models for a ticket and ticket-ingestion request.
- Decide which customer/account fields are necessary; avoid collecting unnecessary sensitive data.
- Add an intake endpoint and tests for valid and invalid payloads.
- Return an acknowledgement only; durable persistence is intentionally not part of this milestone.

**Done when:** API inputs are validated, documented by OpenAPI, and covered by tests. The current endpoint does not persist ticket contents.

### 3. Knowledge base ingestion — next

- Choose supported document formats and an ingestion contract.
- Normalize, split, and track source documents with stable identifiers and metadata.
- Add tests for parsing, chunking, and malformed or empty documents.

**Done when:** sample FAQ/KB documents can be ingested repeatably and their provenance is retained.

### 4. Retrieval (RAG)

- Select an embedding model and vector store based on data size, privacy, and deployment constraints.
- Retrieve relevant passages for a ticket and return source references with each result.
- Measure retrieval quality on a small, representative question set.

**Done when:** retrieval returns relevant, traceable passages and fails safely when evidence is insufficient.

### 5. Classification, routing, priority, and escalation

- Define configurable categories, routing destinations, and explicit escalation rules.
- Produce structured classification and priority recommendations with concise rationales.
- Treat account value, customer tier, and fraud/risk signals as inputs requiring policy review—not as a substitute for it.

**Done when:** representative tickets yield schema-valid recommendations, with tests for edge cases and escalation signals.

### 6. Claude response suggestions

- Add Anthropic through the LangChain integration after configuration and secret handling are in place.
- Ground drafts in retrieved evidence, include source references, and explicitly allow abstention when evidence is missing.
- Require a human to review and approve a draft; do not send replies automatically.

**Done when:** integration tests (mocked by default) cover success, malformed model output, timeouts, and low-evidence cases.

### 7. Evaluation, security, and operations

- Build a small, privacy-safe evaluation set and establish response-quality, retrieval, latency, and escalation baselines.
- Add structured logging without logging secrets or unnecessary customer data.
- Review authentication, rate limiting, retention, access controls, and deployment configuration before production use.

**Done when:** evaluation results are reproducible, operational behavior is observable, and production risks are reviewed.

## Local development (after milestone 1)

Use Python 3.11 or newer.

1. Check that Python 3.11 is available: `python3.11 --version`. On macOS with Homebrew, install it if needed with `brew install python@3.11`.
2. Create (or recreate) and activate the project virtual environment: `python3.11 -m venv --clear .venv` and `source .venv/bin/activate`.
3. Confirm the active interpreter is the virtual environment's Python 3.11: `python --version` and `which python` (the path should end in `/.venv/bin/python`).
4. Install the project and development/test tools into that environment: `python -m pip install --upgrade pip` followed by `python -m pip install -e '.[dev]'`.
5. Run the tests with the same environment: `python -m pytest`.
6. Start the API with the same environment: `python -m uvicorn support_intelligence.api:app --reload --app-dir src`.
7. Open `http://127.0.0.1:8000/docs` for the interactive API docs; check `http://127.0.0.1:8000/health` for health status.

### Troubleshooting Python and pip

Run install and test commands only after activating `.venv`, or call `.venv/bin/python -m ...` explicitly. Do not use the system `python3` if it points to an older Python. This project requires Python 3.11 or newer; the system Python 3.7 and the configured Python 3.9 environment are both too old. An old pip may also fail to install this `pyproject.toml` project. Creating a fresh virtual environment with Python 3.11 provides a compatible interpreter and installer; installing dependencies globally is not needed.

### Temporary Python 3.7 compatibility test

Python 3.7.2 is not a supported project runtime. To let the current API milestone be smoke-tested while Python 3.11 installs, use a separate virtual environment and the legacy test pins. This does not make future LangChain/Anthropic milestones compatible with Python 3.7.

1. Create and activate an isolated environment: `python3 -m venv .venv-py37` and `source .venv-py37/bin/activate`.
2. Upgrade pip within that environment: `python -m pip install --upgrade 'pip<24.1'`.
3. Install the test-only pins: `python -m pip install -r requirements-py37-test.txt`.
4. Run tests without installing the project package: `PYTHONPATH=src python -m pytest`.

Return to the supported Python 3.11 environment for normal development and installation.

## Decisions to make later

- Which vector store and embedding provider fit the KB scale and privacy requirements?
- Will tickets and KB documents be persisted, and where?
- Which ticket categories, teams, escalation policies, and priority weights are configurable?
- What data retention, redaction, authentication, and authorization rules apply?
- Which evaluation dataset and baseline define the claimed response-time/workload improvements?

Do not report the 35% response-time or 40% workload reduction as achieved until measured against an agreed baseline.
