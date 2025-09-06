***
# HiLabs Roster Email → Excel (Local-Only, Open-Source)

## Goal
Convert provider roster emails (**HTML/PDF/Image/XLS/CSV/Inline Text**) into a **clean Excel** matching the required schema—completely end-to-end on your machine, with auditability, version history/rollback, a review UI, and **AI assist (local VLM)** for tough documents.

## Rule Compliance  
- ✅ **Open source code**  
- ✅ **Runs fully locally**: Docker Compose brings up DB, object store, queue, VLM, and SMTP test server  
- ✅ **No uploads** to third-party servers  
- ✅ **No proprietary LLM** calls  
- ✅ Public repo includes **run script and full instructions**

***

## Quick Start (5–10 minutes)

### Prereqs
- macOS / Linux / Windows (WSL2)
- Docker Desktop (Compose v2)
- ~8–12 GB RAM free for services (CPU-only works; GPU optional)

### Run it
```sh
git clone https://github.com/<you>/hilabs-roster.git
cd hilabs-roster
cp .env.example .env   # or use run.sh
./run.sh               # brings up full stack locally
```

***

## Open UIs

- API docs: [http://localhost:8000/docs](http://localhost:8000/docs)
- Review UI: [http://localhost:8000/ui/jobs](http://localhost:8000/ui/jobs)
- Mailpit (test inbox): [http://localhost:8025](http://localhost:8025)
- MinIO (object store): [http://localhost:9001](http://localhost:9001) (`minio` / `minio123`)
- RabbitMQ console: [http://localhost:15672](http://localhost:15672) (`guest` / `guest`)
- Metrics (Prometheus): [http://localhost:8000/metrics](http://localhost:8000/metrics)
- Local VLM service health: [http://localhost:8080/health](http://localhost:8080/health)

***

## Process a Sample

### Option A: via API (using provided samples)
```sh
curl -F "eml=@./samples/Sample-1.eml" http://localhost:8000/ingest
```

### Option B: via Email (into Mailpit)
Send an email (SMTP: `localhost:1025`), then click **“Process to Excel”** in the UI.

### Check Jobs & Export
```sh
curl http://localhost:8000/jobs
curl -X POST http://localhost:8000/jobs/1/export
```

***

## Architecture (Local-Only)

```
               ┌─────────────────────────────────────┐
               │                 UI                  │
               │ Inbox / Review / Versions / Export  │
               └───────────────▲───────────┬────────┘
                               │           │
                         (approve/edit)    │(download Excel)
                               │           │
┌─────────────┐  POST /ingest  │           │         ┌───────────────┐
│  Mailpit    │ ──────────────▶│      ┌────▼───┐     │   MinIO       │
│ (SMTP test) │                 │      │ Export │────▶│ (object store)│
└─────▲───────┘                 │      └───┬────┘     └─────▲─────────┘
      │                         │          │                │
      │ (send email)            │     xlsx │                │
      │                         │          │ raw .eml, att  │
┌─────┴────────┐     Celery     │          │                │
│   FastAPI    │  ──────────────┼──────────┘                │
│ (API/Gateway│    queue        │                           │
│  /UI)       ├─────────────────┘                           │
└─────┬────────┘                                            │
      │                              artifacts / exports ◀──┘
      │
      │  pipeline tasks     ┌─────────────────────────────────────────────┐
      └────────────────────▶│ Multi-Agent Workers (Celery)               │
                            │ Intake→Classify→Extract(rule→VLM)→...      │
                            │ →Normalize→Validate→Version→Export         │
                            └─────────────────────────────────────────────┘
      ▲
      │ SQL (versions, jobs, records, issues)
┌─────┴───────┐
│ PostgreSQL  │
└─────────────┘
```

- Local VLM: FastAPI @ `http://vlm:8080` (MiniCPM-V or CPU fallback)
- Egress guard: blocks outbound HTTP unless allowed

***

## Stack & Why

- **FastAPI:** API + server-rendered review UI, typed, fast, great DX
- **Celery + RabbitMQ:** async, reliable pipelines; parallel jobs
- **PostgreSQL:** versioned records/jobs/exports; easy queries
- **MinIO:** local S3 for raw emails, attachments, artifacts, final Excel
- **Mailpit:** local SMTP inbox for demo/testing
- **Local VLM Service:** hosts MiniCPM-V or CPU fallback (pdfplumber+OCR); no cloud calls
- **Prometheus + OpenTelemetry:** metrics & traces  
- **structlog:** Job-level JSON logs, PHI redaction

***

## Compliance Controls (Default: ON)

- **Local-only:** all services in local Docker
- **Egress guard:** blocks outbound HTTP to non-local hosts
- **No proprietary LLMs:** Open-source VLM only, all local
- **PHI-aware logs:** masks phones, NPIs; no raw PHI in logs

***

## Environment & Config

See `.env.example` (copy to `.env`):
```env
# Core
APP_ENV=local
DATABASE_URL=postgresql+psycopg2://hilabs:hilabs@db:5432/hilabs
S3_ENDPOINT=http://minio:9000
S3_ACCESS_KEY=minio
S3_SECRET_KEY=minio123
S3_BUCKET=hilabs-artifacts

# Queue
CELERY_BROKER_URL=amqp://guest:guest@mq:5672//
CELERY_RESULT_BACKEND=rpc://

# Local VLM
VLM_ENABLED=true
VLM_URL=http://vlm:8080

# Safety: block outbound HTTP beyond localhost
ALLOW_EGRESS=false
```

***

## Services (docker-compose.yml)

| Service     | Purpose                | Port(s)          |
|-------------|------------------------|------------------|
| api         | FastAPI + UI           | 8000             |
| worker      | Celery workers         |                  |
| mq          | RabbitMQ (queue)       | 5672, mgmt 15672 |
| db          | Postgres               | 5432             |
| minio       | S3 object store        | 9000, console 9001|
| mailpit     | SMTP test inbox        | Web 8025, SMTP 1025|
| vlm         | Local VLM server       | 8080             |

***

## Data Model (Versioning & Rollback)

- **emails:** metadata (`message_id`, `from`, `subject`), artifact URI
- **jobs:** process state (`status`, `current_version_id`)
- **versions:** append-only snapshots (author, reason)
- **records:** roster rows for a version (1 row/provider)
- **issues:** validator findings `{level, row, field, message}`
- **exports:** immutable Excel artifacts (URI, checksum, version_id)
- **audit_log:** audit who/when/what for edits/exports/rollbacks

**Mechanics**
- Extraction → Version 1 (system)
- Manual edits → Version 2 (user)
- Export binds to version_id
- Rollback sets current_version_id; re-export as needed

***

## Multi-Agent Pipeline

- **Order:** Intake → Classifier → Extractor (rule-first, VLM assist) → Normalize → Validate → Version → Review → Export  
- **Extractors:**
  - HTML: `pandas.read_html`, BeautifulSoup cleanup
  - XLSX/CSV: Pandas direct
  - PDF: pdfplumber / Camelot
  - Text: line/col inference
- **VLM assist:** For low-confidence/scanned docs, calls local VLM; falls back to rules if VLM unavailable
- **Normalizer:** phones (E.164), dates (MM/DD/YYYY), addresses (usaddress/libpostal), NPI (Luhn)
- **Validator:** required columns, duplicate NPIs, EffDate ≤ TermDate, DOB not future, confidence
- **Version:** snapshot w/issues; status can be needs_review
- **Human Review:** grid edit; issues panel; diff; rollback/version history
- **Exporter:** strict Excel schema/order/types; provenance sheet; stored artifact

***

## Excel Template (strict order)

1. Transaction Type  
2. Transaction Attribute  
3. Effective Date  
4. Term Date  
5. Term Reason  
6. Provider Name  
7. NPI  
8. Specialty  
9. State License  
10. Organization Name  
11. TIN  
12. Group NPI  
13. Address  
14. Phone  
15. Fax  
16. PPG ID  
17. Line of Business  

**Exporter guarantees:**
- Names/order match exactly
- Proper date cells (not strings)
- Text format for ZIP/NPI to preserve leading zeros
- Hidden “Provenance” sheet (job_id, version_id, checksums, timings)

***

## Review UI (Minimal)
- **Inbox:** job list (Pending, Processing, Needs Review, Ready, Exported)
- **Job view:** two-pane: artifact preview + normalized table
- **Issues**: filterable column
- **Buttons:** Re-run, Approve, Export, Rollback
- **Version history:** version list, diff counts, switch/rollback  
- *(HTMX/Jinja; kept simple for hackathon speed)*

***

## API Endpoints (core)

| Method | Endpoint                            | Description                               |
|--------|-------------------------------------|-------------------------------------------|
| POST   | /ingest                             | Upload raw .eml or JSON; returns job_id   |
| GET    | /jobs, /jobs/{id}                   | Get job status, versions, issues, artifacts|
| POST   | /jobs/{id}/process                  | Re-queue process (idempotent)             |
| GET    | /jobs/{id}/versions                 | List versions                             |
| POST   | /jobs/{id}/versions/{vid}/rollback  | Rollback current version                  |
| POST   | /jobs/{id}/export                   | Generate Excel for current version        |
| GET    | /exports/{id}/download              | Stream Excel from MinIO                   |

***

## Training & Adaptation (Local-Friendly, optional)

- **Silver labeling**: auto-label synthetic PDFs/images generated from samples (perturb data, shuffle columns, etc.)
- **PEFT/LoRA fine-tune:** adapters for schema-faithful output; single-GPU, small weights
- **DPO**: align on strict JSON; build (good, slightly wrong) extraction pairs; bias model behavior
- **Continuous learning:** Human edits feed into next round
- **All code local**; zero uploads

***

## Observability

- **Metrics** (`/metrics`)
  - `api_requests_total{path,method,status}`
  - `api_latency_seconds{path}`
  - `agent_runs_total{agent}` / `agent_latency_seconds{agent}`
  - `vlm_invocations_total`, `extract_fallback_total`
  - Pipeline E2E, success/error rates
- **Tracing:** OpenTelemetry per-agent & job-wide trace id.
  - (optional: add Jaeger/Tempo UI)
- **Logging:** `structlog`, job_id/version_id/trace_id, masks for NPIs/phones

***

## Security & Privacy

- **Local-only**: egress guard blocks all non-local HTTP
- **PHI minimization**: stores only required info; no raw PHI in logs
- **Optional**: at-rest artifact encryption (envelope-AES GCM, blind indexes) via env flags (still all local)

***

## Run Script & Portability

`run.sh`
```bash
#!/usr/bin/env bash
set -euo pipefail
# 1) seed env
if [ ! -f .env ]; then cp .env.example .env; fi
# 2) start everything
docker compose up --build
```
*Works on macOS / Linux / Windows (WSL2), only Docker required. Version-pinned for reproducibility.*

***

## Testing & Demo Flow

1. Start stack: `./run.sh`
2. In Mailpit UI, click "Send" (sample attachments also work via /ingest)
3. Open Inbox UI → select job → click "Process to Excel"
4. Review table, fix flagged cells → Approve
5. Click Export, then Download (served from local MinIO)
6. Show version history & rollback
7. Visit `/metrics` for counters/latencies

***

## Troubleshooting

- **Nothing shows in jobs:**  
  Check API logs (`docker compose logs api`) and worker logs (`worker`).  
  Ensure RabbitMQ is up and `CELERY_BROKER_URL` matches.

- **MinIO auth errors:**  
  Confirm `S3_ACCESS_KEY`/`SECRET_KEY`; create bucket in console if needed.

- **Slow PDFs:**  
  Large scans on CPU are slow; limit pages, or prefer likely pages for VLM.

- **Outbound call blocked:**  
  By design. Set `ALLOW_EGRESS=true` only for dev (don’t submit with this on).

***

## Repo Layout (suggested)

```
.
├── api/
│   ├── app/
│   │   ├── main.py            # FastAPI routes + HTMX pages
│   │   ├── config.py          # settings from env
│   │   ├── db.py              # SQLAlchemy engine/session
│   │   ├── models.py          # ORM tables (emails, jobs, versions, records, issues, exports)
│   │   ├── schemas.py         # Pydantic DTOs
│   │   ├── storage.py         # MinIO helpers (put/get objects)
│   │   ├── celery_app.py      # Celery init
│   │   ├── pipeline.py        # task orchestration
│   │   ├── net_guard.py       # outbound HTTP guard
│   │   └── agents/
│   │       ├── intake_email.py
│   │       ├── classifier.py
│   │       ├── extract_rule.py
│   │       ├── extract_pdf.py
│   │       ├── vlm_client.py
│   │       ├── normalizer.py
│   │       ├── validator.py
│   │       └── exporter_excel.py
│   ├── Dockerfile
│   └── requirements.txt
├── vlm/
│   ├── app.py                 # local VLM service (MiniCPM-V/cpu fallback)
│   ├── Dockerfile
│   └── requirements.txt
├── samples/                   # Sample-1.eml, Sample-2.eml, Sample-3.eml
├── docker-compose.yml
├── .env.example
├── run.sh
├── README.md                  # (this doc)
└── docs/ARCHITECTURE.md       # (deeper theory, diagrams - optional)
```

***

## Extensibility (Post-Hackathon)

- Swap MinIO ↔️ S3 (just change env values)
- Replace HTMX with Next.js SPA (API unchanged)
- Scale: add more worker replicas
- For new rules, deploy VLM & API on GPU, keep `/infer` contract

***

## Why it will score well

- One-click processing in inbox-like UI  
- Multi-agent AI with open-source VLM (rule-first, efficient)  
- Version history + rollback (with diff, cell-level)  
- Robust validation (NPI/phone/date/address/duplicate)  
- **Observability:** Production-grade metrics & tracing  
- **Local-only, open source, reproducible—zero cloud dependencies**

***

## Appendix: Validation Rules (Summary)

- Required columns present (exact schema)
- Parseable phone (US default); E.164 normalization
- Parseable dates; output as MM/DD/YYYY
- NPI: 10-digit Luhn with 80840 prefix logic
- Address: parse + confidence tracking
- Detect duplicate NPIs
- Effective Date ≤ Term Date, DOB not in future
- "Information not found" for missing required cells at export

***

## Appendix: Performance Tips (Local)

- Use CPU-first parsers; VLM only on flagged pages
- For large PDFs: downsample/cap page count
- Try quantized MiniCPM-V models for faster local inference

***
