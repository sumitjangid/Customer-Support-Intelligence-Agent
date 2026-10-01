# Evaluation, Security, and Operations

## Scope and current status

This is a local prototype, not a production-ready support system. The benchmark data in `evaluation/` is synthetic and hand-authored. The offline triage evaluator checks deterministic rule behavior; it does not establish real-world accuracy, fairness, business impact, or the claimed 35%/40% improvements. Gemini retrieval and draft-quality evaluation remain manual because live calls use external API quota and generated text is variable.

## Run the offline triage evaluation

From the repository root with the Python 3.11 project environment:

```text
.venv/bin/python -m support_intelligence.evaluate
```

For machine-readable output:

```text
.venv/bin/python -m support_intelligence.evaluate --json
```

The evaluator reads `evaluation/triage-cases.json`, runs local deterministic rules only, and reports exact-match category/team/priority-band/escalation/human-review metrics. It makes **no Gemini calls**, needs no API key, and never prints the ticket text. A non-zero exit code indicates at least one labeled case failed. Update the dataset only with synthetic or approved de-identified fixtures, and review labels independently of the rules being evaluated.

The current ten hand-authored cases yield 100% exact match because they encode the present prototype rules. This is a regression check, not independent validation. Add held-out and edge cases before treating metrics as evidence of performance. Track class-level confusion, false negatives for escalations, and abstention behavior; the overall accuracy alone can hide unsafe misses.

## Retrieval evaluation

`evaluation/retrieval-cases.json` contains synthetic search queries and expected source documents. To assess retrieval, rebuild the local index and query each case with the CLI:

1. `PYTHONPATH=src .venv/bin/python -m support_intelligence.retrieve index knowledge_base`
2. For each query, run `PYTHONPATH=src .venv/bin/python -m support_intelligence.retrieve search "<query>" --top-k 3`.
3. Record whether at least one expected source is returned in the top results (Recall@k), its rank (reciprocal rank), and whether unsupported questions have no sufficiently relevant evidence.
4. Repeat after changes to chunk size, overlap, embedding model, or retrieval threshold. Rebuild embeddings when changing the embedding model.

This live test sends the query and any indexed text to Gemini. Use dummy/public content only; API use is subject to changing rate limits, free-tier terms, and prompt-retention policies.

## Response quality review

Use `evaluation/response-cases.json` as a manual checklist for grounded drafting, abstention on unsupported questions, citation correctness, prompt-injection handling, and the human-review marker. For each case, capture whether the result is a draft or abstention, whether every source exists in the local result set, and whether the draft adds any unsupported promise or policy. Never judge solely on fluency. Do not write API keys, real tickets, or customer content to evaluation outputs.

## Security and privacy review

### Prototype controls in place

- Ticket intake, triage, response suggestion, and combined processing are stateless; no ticket records are persisted.
- The API key belongs only in ignored local `.env`; `.env.example` is a placeholder. Never commit or paste a key into source, issues, or chat. Restrict the key to the Gemini API in AI Studio where available, monitor usage, and rotate it if exposed.
- `.local/knowledge-index.json` is ignored by Git and written atomically with owner-only file permissions. It contains original chunk text as well as embeddings; protect it like the source documents.
- Gemini receives the ticket subject/description, the retrieval query, and relevant knowledge chunks when generating embeddings/drafts. Free-tier terms may allow content use for service improvement and abuse monitoring. Only synthetic/public data is allowed for this prototype.
- The generation prompt treats ticket and KB text as untrusted data. Citations are checked against retrieved chunk IDs; low-evidence cases abstain; drafts are always marked for human review and are never sent.
- API handlers do not log request bodies. Preserve this rule; avoid logging prompts, ticket text, source contents, API keys, or model responses by default.

### Risks and production requirements (not implemented)

- **No API authentication/authorization:** the prototype endpoints are open. Bind local development to `127.0.0.1`; never expose the development server to a LAN or public network. Production requires authentication, authorization, TLS, and appropriate tenant isolation.
- **No rate limiting or request quotas:** protect public endpoints before deployment. Apply body-size limits, per-user quotas, timeouts, provider retry/backoff limits, and spend alerts.
- **No durable store or retention policy:** if storage is introduced, define access control, encryption, retention/deletion, backups, and audit requirements first.
- **Heuristic bias and errors:** keyword-based classification, anger, fraud, account risk, and priority are fallible. Keep the factor breakdown visible, require human review for escalations, and evaluate false negatives and disparate impact before use.
- **Prompt injection and untrusted KB:** current prompt instructions are a mitigation, not a guarantee. Keep tools/actions out of the drafting path, validate all structured output, verify citations in application code, and test hostile ticket and document content.
- **Dependency and model drift:** pin/review dependency updates, record the embedding model in the local index, and rebuild/re-evaluate after model, prompt, or rule changes.
- **No production observability:** add privacy-safe metrics for latency, provider errors, retrieval score distributions, abstentions, review outcomes, and estimated cost. Do not include raw ticket contents in telemetry.

## Success measures and business claims

Define a baseline before claiming response-time or workload improvement. Suggested measures include median and p95 first-response time, agent handling time, deflection/approval rate, retrieval Recall@k, grounded-draft acceptance rate, unsupported-claim rate, and escalation precision/recall. Compare the same representative workflow before and after, document sample size and dates, and retain human review for the evaluation. The project brief's 35% response-time and 40% workload figures remain unverified targets.
