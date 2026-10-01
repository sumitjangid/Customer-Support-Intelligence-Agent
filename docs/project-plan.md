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

### 3. Knowledge base ingestion — complete

- Read local UTF-8 Markdown (`.md`) and plain-text (`.txt`) files recursively from `knowledge_base/`.
- Normalize line endings, split content into deterministic overlapping chunks, and attach source path, content hash, and stable IDs.
- Ignore empty documents and unsupported extensions; report invalid UTF-8 as an actionable ingestion error.
- Keep ingestion local and stateless: no database, embeddings, vector store, or provider calls in this milestone.
- Add tests for parsing, chunking, metadata, repeatability, invalid documents, and settings.

**Done when:** sample FAQ/KB documents can be ingested repeatably and their provenance is retained. The CLI prints a summary; it does not persist generated chunks. Validated with 14 passing tests and a CLI smoke test against `knowledge_base/returns.md`.

### 4. Retrieval (RAG) — complete

- Use Gemini Embedding 2 as an optional free-tier prototype provider for synthetic/public text; its current embedding docs require task-prefixed queries and title/text-formatted documents.
- Persist embeddings and source chunks in a local JSON index under ignored `.local/`; rank with cosine similarity without a hosted vector database.
- Return source path, chunk index, similarity score, and excerpt in local CLI searches.
- Keep the API key in an ignored `.env` file and never commit it. The Gemini API receives KB chunks and queries; do not use confidential or real customer data under this prototype setup.
- Keep provider access optional and mock it in tests; no real API key is required for the automated test suite.
- Treat the free tier and quotas as subject to change; verify current terms before using the service.

**Done when:** retrieval returns relevant, traceable passages and fails safely when evidence is insufficient. Validated with 21 passing tests on Python 3.11, one successful live Gemini Embedding 2 request (dummy text only), and a local semantic-search smoke test returning the matching `returns.md` passages with source path, chunk index, and cosine score.

### 5. Classification, routing, priority, and escalation — complete

- Add a stateless `POST /tickets/triage` endpoint with validated, bounded inputs.
- Start with transparent keyword rules for billing, shipping, product, and general categories and configurable team destinations.
- Score priority from explicit severity, customer tier, account-value band, and escalation signals; return factor-by-factor rationale.
- Flag possible angry tone, account risk, and fraud indicators; these are heuristics, not verified findings or autonomous decisions.
- Require human review for P1 and any escalation flag; do not execute routing or customer actions.
- Keep personally identifying/account details out of the prototype triage fields and add tests for ambiguous and invalid inputs.
- Provide `POST /tickets/process` to accept ticket content and triage signals once, then return triage and a response draft/abstention together. It remains stateless; its generated ticket ID is only a correlation ID.
- Map missing local index and Gemini provider/rate-limit failures to explicit API errors rather than crashing the application.

**Done when:** representative tickets yield schema-valid, explainable recommendations, with tests for categories, routing, priority boundaries, escalation signals, ambiguity, and validation. Completed with 30 passing tests on Python 3.11. The ruleset remains a prototype to tune against an approved evaluation set.

### 6. Gemini response suggestions — complete

- Use the existing Gemini API key and Google GenAI SDK for structured response generation; do not add or expose another provider secret.
- Retrieve source chunks from the local vector index and send only the synthetic ticket subject/description plus retrieved dummy/public passages to Gemini.
- Use structured JSON output with citations restricted to retrieved chunk IDs; resolve citations to source paths in application code.
- Abstain without calling the generator when no sufficiently relevant evidence is found; also support model-directed abstention.
- Treat ticket/KB contents as untrusted data and ignore embedded instructions. Do not invent policy or claim a reply/action was sent.
- Return a draft and its sources for human approval only; no sending endpoint or autonomous response action.
- Mock model and embedder in tests. Gemini's free-tier availability, quota and data terms can change.

**Done when:** tests cover grounded drafts, validated citations, provider failures, and low-evidence abstention; completed with 40 passing tests and a successful live synthetic-data Gemini smoke test using structured output. The response suggestion remains a prototype and requires human approval.

### 7. Evaluation, security, and operations — next

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

### Ingest local knowledge files

Add UTF-8 `.md` or `.txt` files under `knowledge_base/`, then run `PYTHONPATH=src python -m support_intelligence.ingest knowledge_base` from the repository root. Optionally set `--chunk-size` and `--overlap`; overlap must be smaller than chunk size. The command reports how many supported documents and chunks were found. At this stage, chunk text is returned by the Python ingestion function but is not written to disk or indexed.

### Gemini embedding retrieval experiment

This optional experiment uses an external API only for embeddings; vector search and the persisted index remain local. Use synthetic/public documentation only. The API key is a secret and must never be pasted into chat or committed.

1. Install optional dependencies: `python -m pip install -e '.[dev,gemini]'`.
2. Copy `.env.example` to `.env` and put your Google AI Studio API key in the local `.env` file.
3. Build or rebuild the local index: `python -m support_intelligence.retrieve index`.
4. Search: `python -m support_intelligence.retrieve search "When can I return an item?"`.
5. The ignored `.local/knowledge-index.json` stores both vectors and chunk text. Keep it local; it is excluded from Git.

Gemini's free tier has limits and data terms that can change. Current pricing says free-tier content may be used to improve Google products. Confirm current terms and use only dummy/public content. This embedding experiment is the retrieval stage; response drafting is handled separately in the response-suggestion milestone below.

### Gemini response-suggestion prototype

The `POST /tickets/suggest-response` endpoint queries the local index, filters weak matches, then uses Gemini structured output to draft an evidence-based reply. The generation request contains the synthetic ticket subject/description and retrieved evidence text; the customer reference is not sent. Citation IDs are checked against retrieved chunks and mapped to source paths locally. If retrieval is weak, the endpoint abstains without calling Gemini. Every draft is explicitly marked for human review and is never sent. Use the endpoint in `/docs` or submit a synthetic ticket with the existing API test client. Free-tier terms can allow prompt retention and use for service improvement, so never submit real support/customer information.

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
