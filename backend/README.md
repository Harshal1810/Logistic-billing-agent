# Logistic Billing Agent Backend

## Problem summary
Freight bills often arrive with partial references, overlapping contracts, pricing revisions, and duplicate/cumulative billing risk. This backend resolves candidate contract/shipment context, runs deterministic financial validations, and pauses for human review when ambiguity or risk is high.

## Architecture overview
- FastAPI: API layer for ingest, workflow status, review queue, and review submission.
- Postgres: source of truth for freight bills, candidate matches, validations, decisions, review tasks, and `agent_runs` workflow state.
- Neo4j: relationship traversal for candidate matching and graph-based context lookup.
- LangGraph: workflow orchestration with deterministic node order, review interrupt, and durable resume.

## Why this design
- Deterministic rules own money math: charges, rates, weights, dates, and contract validity are computed in Python services.
- Graph traversal owns ambiguity: overlapping contracts and shipment inference are better modeled via connected entities.
- LangGraph owns state transitions: it controls progression/pauses/resume, but does not implement business math.
- LLMs are used only for grounded human-readable explanations, never for matching, validation, scoring, or final decision policy.

## LLM usage (explanations only)
- Purpose:
  - Generate `decision_explanation` for `freight_bill_decisions`.
  - Generate `review_summary` for `review_tasks`.
- Grounding:
  - Prompt input is strictly structured evidence already produced by the system (selected matches, validations, decision, confidence, review context).
  - Explanations cannot change any deterministic output.
- Provider/model selection:
  - Primary: OpenAI (`OPENAI_API_KEY`) with default model `gpt-5-mini`.
  - Fallback provider: Groq (`GROQ_API_KEY`) with default model `llama-3.3-70b-versatile`.
  - Final fallback: deterministic template text when LLM is unavailable/fails.
- Reliability:
  - If provider call fails or times out, workflow still completes with deterministic fallback explanations.
- LLM usage is intentionally narrow and optional in this implementation; deterministic services handle contract/date/rate/weight validation, while the workflow architecture leaves room for future name normalization or explanation generation

## How to run locally
Recommended Python version: `3.11` (tested with the current dependency set).

```bash
cd backend
python -m venv .venv
# Windows PowerShell
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate
pip install -r requirements.txt
#Start Docker Desktop
docker compose up -d
alembic upgrade head
# Loads master/reference data only (excludes freight_bills by default)
python -m scripts.load_seed
python -m scripts.project_to_neo4j
uvicorn app.main:app --reload
```

To preload freight bills from seed as well:
```bash
python -m scripts.load_seed --include-freight-bills
```

Run tests:
```bash
python -m scripts.test_langgraph_workflow
python -m scripts.test_langgraph_restart_resume
python -m scripts.test_business_scenarios
```

## Streamlit UI (Ops Console)
Use the Streamlit app to hit APIs and inspect live workflow state in a user-friendly format.

Run:
```bash
cd backend
pip install -r requirements.txt
streamlit run streamlit_app.py
```

Main tabs:
- `Ingest`: send `POST /freight-bills` payloads (seed picker + JSON editor + force reprocess).
- `Current Bills`: call `GET /freight-bills` to list currently ingested bills and open one in explorer.
  - Includes one-click reset for freight-bill state in Postgres + Neo4j (with confirmation).
- `Bill Explorer`: fetch `GET /freight-bills/{id}` and inspect overview, candidates, validations, decision, workflow, audit.
- `Review Queue`: inspect `GET /review-queue` and submit `POST /review/{id}` actions.
- `Graph`: visualize FreightBill -> Carrier/Contract/Shipment/BOL context plus top candidates.

## Environment variables
Add these to `backend/.env`:

```env
DATABASE_URL=postgresql+psycopg://logistics_user:logistics_pass@localhost:5433/logistics_db

NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=neo4j_pass

# LLM explanation providers (OpenAI preferred, Groq fallback)
OPENAI_API_KEY=
OPENAI_MODEL=gpt-5-mini
OPENAI_TIMEOUT_SECONDS=8.0

GROQ_API_KEY=
GROQ_MODEL=llama-3.3-70b-versatile
GROQ_TIMEOUT_SECONDS=8.0
```

## API endpoints
- `POST /freight-bills`
  - Ingests a freight bill payload and starts (or re-runs) workflow orchestration.
- `GET /freight-bills`
  - Lists currently ingested freight bills with processing/decision/selection state.
- `GET /freight-bills/{id}`
  - Returns bill data, selected/candidate matches, validations, decision, confidence, workflow state, review task state, and audit summary.
- `GET /review-queue`
  - Returns pending review tasks with top candidates, validation issues, and suggested decision.
- `POST /review/{id}`
  - Submits reviewer action (`approve|dispute|modify`) and resumes workflow from persisted state.
- `POST /admin/reset-freight-bills`
  - Deletes all ingested freight bills and related workflow outputs in Postgres, and removes `FreightBill` nodes from Neo4j.

## How the bill is processed
1. Ingest freight bill into Postgres.
2. Project and traverse graph context in Neo4j.
3. Rank contract and shipment candidates.
4. Persist selected matches.
5. Run deterministic validation rules.
6. Compute confidence and preliminary decision.
7. Either finalize or create review task.
8. Resume from persisted state after reviewer action.

## Data model
- `carriers`: carrier master data and status.
- `carrier_contracts`: contract periods and contract-level metadata.
- `contract_rate_cards`: lane-level pricing and surcharge terms.
- `shipments`: shipment execution records tied to carrier + contract.
- `bills_of_lading`: shipment delivery/actual weight evidence.
- `freight_bills`: ingested bill payload, selected matches, workflow/decision state.
- `freight_bill_candidate_matches`: scored contract/shipment/BOL candidates.
- `freight_bill_validations`: per-rule validation outcomes.
- `freight_bill_decisions`: persisted decision + confidence + reason.
- `review_tasks`: human review queue items and reviewer decision payload.
- `agent_runs`: durable workflow state (`run_id`, `current_node`, `state_payload`, status, errors).

## Neo4j graph model
Node types:
- `Carrier`
- `CarrierContract`
- `Lane`
- `Shipment`
- `BOL`
- `FreightBill`

Relationships:
- `(Carrier)-[:HAS_CONTRACT]->(CarrierContract)`
- `(CarrierContract)-[:COVERS_LANE]->(Lane)`
- `(Carrier)-[:HANDLED]->(Shipment)`
- `(CarrierContract)-[:GOVERNS]->(Shipment)`
- `(Shipment)-[:HAS_BOL]->(BOL)`
- `(FreightBill)-[:BILLED_BY]->(Carrier)`
- `(FreightBill)-[:REFERENCES_SHIPMENT]->(Shipment)` (when source reference exists)

Why Neo4j helped:
- Finds candidates under overlapping contracts and lane constraints.
- Supports shipment inference when invoice references are weak/missing.
- Makes ambiguous relationship traversal easier, especially for overlapping contracts, shipment inference, and tracing related billing context.

## Validation rules
Contract and pricing rules:
- `contract_validity`
- `lane_match`
- `rate_validation`
- `base_charge_validation`
- `unit_reconciliation`
- `contract_shipment_consistency`

Invoice arithmetic rules:
- `amount_consistency`
- `fuel_surcharge_check`

Shipment/BOL reconciliation rules:
- `shipment_resolution`
- `carrier_resolution`
- `weight_reconciliation`

Workflow/risk rules:
- `duplicate_bill_check`
- `cumulative_billing_check`

## Confidence + decision policy
- Confidence starts at `1.0` and is reduced by severity/rule penalties (critical/high/medium/low), clamped at `0.0`.
- `auto_approve`: no blocking fails, no warnings requiring manual handling, and resolved selections.
- `flag_for_review`: warnings/ambiguity/missing selections/unknown carrier cases that require human judgment.
- `dispute`: hard validation failures (for example duplicate/overbilling/major reconciliation issues) that should not auto-approve.
- Critical failures such as duplicate billing or confirmed cumulative over-billing heavily reduce confidence and usually force dispute, while warnings and unresolved ambiguity lower confidence and route the bill to review.

## Human-in-the-loop flow
- Review gate: LangGraph transitions to `waiting_for_review` when risk/ambiguity requires manual action.
- `review_tasks`: pending task created with interrupt payload and reviewer context.
- Durable resume: `agent_runs.state_payload` + `current_node` are persisted in Postgres and used as resume source of truth.
- Restart safety: process restart does not lose run context; resume continues from review path.
- Reviewer handling: `POST /review/{id}` applies reviewer decision (`approve|dispute|modify`), enforces strict transitions, and finalizes idempotently.

## Supported seed scenarios
- Clean match and auto-approve.
- Overlapping contracts requiring scoring.
- Duplicate bill detection.
- Rate drift detection.
- Expired contract detection.
- Unit reconciliation across billing models.
- Fuel surcharge revision handling.
- Unknown carrier routed to review.
- Over-billing / cumulative risk detection.

## Tests
- Workflow path tests: `scripts/test_langgraph_workflow.py`
- Restart/resume durability test: `scripts/test_langgraph_restart_resume.py`
- Business scenario tests: `scripts/test_business_scenarios.py` (105/106/107/108/110)

## Trade-offs / what I’d do next
- Stricter Postgres-backed checkpointing integration across every node edge.
- Richer reviewer override flows (e.g., override selected contract/shipment with audit reason).
- Better duplicate heuristics (fuzzy invoice refs + temporal/amount similarity windows).
- Production hardening: authN/authZ, retries, async workers, rate limits, and observability dashboards.

## Mermaid workflow diagram
```mermaid
flowchart TD
    A[POST /freight-bills] --> B[Persist freight_bill in Postgres]
    B --> C[Start LangGraph run]
    C --> D[Match contract candidates via Neo4j]
    D --> E[Match shipment/BOL candidates via Neo4j]
    E --> F[Run deterministic validations in Python]
    F --> G[Compute confidence + decision]
    G --> H{Needs review?}

    H -- No --> I[Finalize decision]
    I --> J[Update freight_bill + decision + agent_run]

    H -- Yes --> K[Create review_task]
    K --> L[Set agent_run waiting_for_review + persist state_payload]
    L --> M[GET /review-queue]
    M --> N[POST /review/{id}]
    N --> O[Resume from persisted current_node/state_payload]
    O --> P[Apply reviewer decision]
    P --> I
```
