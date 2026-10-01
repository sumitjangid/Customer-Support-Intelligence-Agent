# Customer Support Intelligence Agent

A Python-based support-ticket assistant designed to help teams find relevant knowledge-base guidance, triage incoming tickets, prioritize urgent cases, and draft responses for human review.

> **Project status:** The API foundation, validated stateless ticket intake, local knowledge ingestion, local semantic retrieval, deterministic ticket triage recommendations, and Gemini response-suggestion prototype are in place. Evaluation/security/operations work and measured performance results remain future work.

## Documentation

- [Step-by-step project plan](docs/project-plan.md) — milestones, local setup, acceptance criteria, and decisions to make.
- [Architecture](docs/architecture.md) — target workflow, proposed module boundaries, and safety constraints.

## Quick start

Follow the [development guide](docs/project-plan.md#local-development-after-milestone-1) to install the package, run tests, and start the API.

For the temporary Python 3.7.2 test path, see [Python 3.7 compatibility testing](docs/project-plan.md#temporary-python-37-compatibility-test).

## Ingest local knowledge files

Place UTF-8 Markdown (`.md`) or plain-text (`.txt`) files under `knowledge_base/`. To preview the ingestion summary, run `PYTHONPATH=src python -m support_intelligence.ingest knowledge_base`. The reader returns deterministic chunks with source metadata; it does not persist content or generate embeddings.

## Semantic retrieval prototype

The retrieval experiment sends only the synthetic/public KB text and search query to Google's Gemini Embedding API; chunk text and vectors are stored in an ignored local `.local/knowledge-index.json` file. Install the optional provider and test dependencies with `python -m pip install -e '.[dev,gemini]'`, copy `.env.example` to `.env`, and add a Google AI Studio API key there. Build an index with `python -m support_intelligence.retrieve index`, then search it with `python -m support_intelligence.retrieve search "When can I return an item?"`. The local index does not require a hosted vector database. Gemini free-tier availability, quotas, model availability, and data terms can change; do not use confidential or real customer data with this prototype.

## Ticket triage prototype

The stateless `POST /tickets/triage` endpoint uses transparent keyword rules to recommend a category/team and an urgency score from severity and explicit customer/account bands. It reports matching terms and score factors. Text-based anger, account-risk, and fraud signals are heuristics that can be wrong; they only request human review. The endpoint never routes a ticket or takes a customer-facing action.

## Gemini response suggestion prototype

After creating the local index, open `http://127.0.0.1:8000/docs` and try `POST /tickets/suggest-response` with the sample returns FAQ and synthetic ticket text. The service returns a draft with verified local source references, or abstains if retrieval has insufficient evidence. All drafts require human review and are never sent. The Gemini request includes ticket subject/description and retrieved chunk text, but excludes the customer reference. Free-tier data handling and quotas may change; use dummy/public content only.

## Combined ticket workflow

Use `POST /tickets/process` to submit the ticket once and receive both the triage recommendation and response suggestion (draft or abstention). The request accepts the same triage fields as `/tickets/triage`; the response includes a generated correlation ID and processing timestamp. The endpoint remains stateless: the ID cannot be used to fetch a stored ticket, and no draft is sent. Try it in `http://127.0.0.1:8000/docs` with the synthetic return question. If the local index is missing, it returns 503; Gemini provider failures or rate limits are reported as a gateway error, so wait and retry later.

## Goals

- Ingest internal knowledge-base articles and FAQs and retrieve relevant material for a support ticket using retrieval-augmented generation (RAG).
- Suggest a response grounded in retrieved support documentation; keep a human in the loop before sending.
- Classify tickets into configurable categories such as billing, shipping, and product issues, then recommend a team.
- Flag possible escalations, including angry or distressed language, account-risk signals, and fraud indicators.
- Score urgency using signals such as customer tier, account value, and issue severity, and highlight cases for human review.
- Keep the workflow modular so categories, routing rules, and escalation signals can evolve independently.

## Intended workflow

1. **Ticket ingestion** — validate incoming ticket data.
2. **Knowledge retrieval** — find relevant internal KB/FAQ content.
3. **Classification and routing** — determine issue category and suggested team.
4. **Priority and escalation assessment** — identify urgent or sensitive cases.
5. **Response suggestion** — draft a grounded response and present the evidence and recommendation for agent review.

## Planned technology

- Python
- FastAPI
- Pydantic
- Gemini API (prototype embeddings and response generation)
- Anthropic Claude / LangChain (future provider options to evaluate)

Specific model, vector store, persistence layer, and deployment choices will be documented as they are selected during implementation.

## Development roadmap

1. API foundation and health check.
2. Ticket domain models and intake endpoint.
3. Knowledge-base ingestion and source tracking.
4. Retrieval and relevance evaluation.
5. Classification, routing, priority, and escalation recommendations.
6. Gemini response suggestions with human approval (prototype provider; evaluate provider choice before production).
7. Evaluation, security, and operational readiness.

See the [step-by-step project plan](docs/project-plan.md) for acceptance criteria for each milestone.

## Performance targets

The project brief includes goals of reducing response time by **35%** and support-team workload by **40%**. These are targets to evaluate against a documented baseline; they are not measured or verified results at this stage.

## Safety and review

The system is intended to assist support staff, not make final decisions autonomously. Suggested replies, routing, and escalation decisions should be reviewable by a human, with the supporting knowledge sources visible. Sensitive signals such as fraud or account risk should be handled according to the eventual organization's policies.

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE).
