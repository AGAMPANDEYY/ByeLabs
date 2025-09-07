<h1>
  <img src="assets/byelabs_wordmark_compact.svg" alt="ByeLabs" height="28" />
  HiLabs Roster Automation (Scalable, Local-first, Multi-Agent, SLM-GRPO RL Training)
</h1>


> **Touchless end-to-end roster processing** — from raw emails (`.eml`, PDFs, images, HTML tables, CSV/XLSX) to a perfectly formatted Excel in one click.
> **Everything runs 100% locally** (no proprietary APIs, no third-party uploads).
> Built with a **multi-agent pipeline**, **open-source LLM**, RL training with Group Reward Policy Optimisation policies on synthetic dataset, versioning + rollback, analytics, and production-style observability.

**Video Demo** : [link](https://drive.google.com/file/d/1UGrqXEa0UGTlACpZGqsCPc3Td0zcPvym/view?usp=sharing)

---

## We thought Scailibity, Architectures and AI!

* **Local-only by design:** All parsing, model inference, training, storage, and analytics run on your machine with Docker/Compose or a single Python env. Zero calls to closed APIs.
* **Agentic AI + Rules:** A **multi-agent** workflow that prefers deterministic parsers first, then escalates to **open-source SLM (Qwen3-4B-Instruct)** to crush tricky PDFs/scans.
* **Data quality you can trust:** Strong normalization + validation (NPI Luhn, phone, address, dates, duplicates, schema checks) and **human-in-the-loop review**.
* **Auditability built-in:** Every change creates a **version**; export binds to a version; you can **diff & rollback** anytime.
* **Observability like production:** Metrics, logs, and traces (Prometheus + OpenTelemetry + Grafana) so judges can *see* the system working.
* **Research-grade training:** We finetuned a **small language model (SLM)** with **GRPO** (Group-Relative Policy Optimization) using **silver-labeled weak supervision** + LoRA adapters, so it learns our schema and avoids hallucinations.

> We optimized for **hackathon reality**: limited time, no external services, but architected for **scale and maintainability** if this graduates into a product.

---

##  System Overview

<img width="3768" height="1680" alt="image" src="https://github.com/user-attachments/assets/5f71758e-8f08-4c67-8e21-5042c761cf2e" />


## Quick Start Guide

### Prerequisites
- Docker and Docker Compose installed
- Python 3.11+ (for local development)
- Node.js 18+ (for frontend development)
- Git

### 1. Clone and Setup

```bash
git clone https://github.com/AGAMPANDEYY/ByeLabs.git
cd ByeLabs
```

### 2. Start Backend Services (Docker)

```bash
docker-compose -f docker-compose.simple.yml up -d
```

### 3. Start Frontend (Local)

```bash
cd web
npm install
npm run dev
```

### 4. Setup LLM Service (Optional)
```bash
# Download model

mkdir -p models
cd models
wget https://huggingface.co/P3g4su5/ByeLabs-LoRA/resolve/main/adapter.gguf

# Start llama.cpp server
cd ..

# For CPU Inference
docker run -d --name llama-server \
  -p 5000:8080 \
  -v $(pwd)/models:/models \
  ghcr.io/ggerganov/llama.cpp:server \
  -m /models/adapter.gguf \
  --host 0.0.0.0 --port 8080

# For GPU Inference
docker run -d --name llama-server \
  --gpus all \
  -p 5000:8080 \
  -v $(pwd)/models:/models \
  ghcr.io/ggml-org/llama.cpp:server-cuda \
  -m /models/adapter.gguf \
  --host 0.0.0.0 --port 8080
```

### 5. Test the System
```bash
# Test API health
curl http://localhost:8000/health

# Upload test email
curl -X POST -F "file=@test_email.eml" http://localhost:8000/ingest

# Check job status
curl http://localhost:8000/jobs/1

# Download Excel export
curl -O http://localhost:8000/exports/1/download
```

### 6. Access Web Interface
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs
- Llama cpp : port 5000

### 7. Monitor Logs
```bash
# Backend logs
docker-compose -f docker-compose.simple.yml logs -f api

# Worker logs
docker-compose -f docker-compose.simple.yml logs -f worker

# All services
docker-compose -f docker-compose.simple.yml logs -f
```

### 8. Stop Services
```bash
# Stop all services
docker-compose -f docker-compose.simple.yml down

# Stop and remove volumes
docker-compose -f docker-compose.simple.yml down -v
```

### 10. Troubleshooting
```bash
# Check container status
docker ps

# Restart specific service
docker-compose -f docker-compose.simple.yml restart api

# View container logs
docker logs byelabs-api-1

# Clean up Docker
docker system prune -a
```

### System Architecture
- **Backend**: FastAPI + PostgreSQL + MinIO + RabbitMQ + Celery
- **Frontend**: Next.js 14 + TypeScript + Tailwind CSS
- **LLM**: Local llama.cpp server with **Qwen3-4B-Instruct** model
- **Processing**: Multi-agent pipeline with spaCy NLP + LLM extraction
- **Storage**: MinIO for files, PostgreSQL for metadata
- **Queue**: RabbitMQ + Celery for async processing

---

## Features

* **Email ingestion:** `.eml` upload (and optional local SMTP via Mailpit) with attachment handling.
* **Format coverage:** HTML body tables, CSV/XLSX, native PDFs, scanned PDFs/images.
* **Multi-agent pipeline:** Intake → Classification → Extraction (rules) → **LLM fallback** → Normalization → Validation → Versioning → Excel export.
* **SLM (local LLM):** fine-tuned via **GRPO** with LoRA adapters.
* **Normalization:** phone (E.164), address (usaddress/libpostal), dates (dateparser with `MDY`), NPI checksum (Luhn with `80840`).
* **Validation:** required fields, enumerations, duplicates, cross-field rules, confidence thresholds.
* **Review UI:** spreadsheet-like editor, side-by-side original preview, issues list, **diff + rollback**.
* **Exports:** exact Excel template with correct column order/types and hidden provenance sheet.
* **Observability:** per-stage timing, fallback rates, error heatmaps, traces spanning the whole job.

---

## Training the local SLM with **GRPO**

**Goal:** make a small local model reliably output schema-exact JSON rows from messy text/PDF extractions.

* **Training Dataset:**
  * Rigorously prompting **Gemini 2.5 Pro** to craft variety of emails
  * Programmatically **augmenting** structures (names, NPIs, phones, addresses, row permutations, header variants).

* **Reward design (per sample):**
  * **Completeness** (required fields present)
  * **Accuracy** (matches canonical/normalized values)
  * **Format** (NPI/phone/date/address format rules)
  * **Consistency** (cross-field constraints, duplicates)

* **GRPO (Group-Relative Policy Optimization):**
  * For each prompt, sample multiple candidate outputs from the SLM (group).
  * Score each with the reward function.
  * Optimize the policy to increase probability of higher-scoring candidates **relative** to lower-scoring ones in the same group (stable, offline-friendly alternative to standard RLHF).
  * Implemented as a lightweight custom trainer on top of 🤗 Transformers + PEFT (LoRA) + UnslothAI, fully **offline**.

* **Why GRPO here?**
  With tiny data and strict schema, **relative, reward-shaped learning** aligns the SLM to *prefer* well-formed, schema-valid outputs and reject hallucinations.

> All training/inference runs locally (CPU okay; GPU recommended). No external API calls.

---

## Multi-Agent pipeline (logic you can reason about)

**Rule-first. AI-assist only when needed.** That’s how we keep it fast, cheap, and reliable.

1. **Intake Agent** – parse `.eml`, extract HTML/text/attachments, store raw artifacts to MinIO; create a `job`.
2. **Classifier Agent** – route to HTML/CSV/XLSX/PDF-native/PDF-scan/plain-text pipelines; choose tools + thresholds.
3. **Extractor (rules)** –

   * HTML → `pandas.read_html` (+ BeautifulSoup cleaning)
   * CSV/XLSX → `pandas.read_csv/excel`
   * PDF-native → `pdfplumber` + `camelot` lattice/stream (pick max coverage/headers)
   * Plain text → table inference + regex heuristics
4. **LLM Assist (optional)** – **Qwen3-4B-Instruct** for low-confidence segments; prompts are schema-aware and ask for **JSON only**.
5. **Normalizer** – `phonenumbers`, `usaddress/libpostal`, `dateparser`, **NPI Luhn**; log changes + confidences.
6. **Validator** – required fields, enumerations, duplicates, cross-field (e.g., effective ≤ termination), per-cell issues with suggestions.
7. **Versioner** – snapshot rows; every edit creates a new **version**; **rollback** anytime.
8. **Exporter** – write Excel template (openpyxl/xlsxwriter) with exact sheet/columns/types; add hidden provenance sheet.

---

## Tech Stack

* **Frontend:** Next.js (App Router), TypeScript, TailwindCSS, shadcn/ui, TanStack Table.
* **API:** FastAPI, Pydantic v2, SQLAlchemy 2.
* **Workers/Queue:** Celery + RabbitMQ (async, scalable).
* **Data layer:** PostgreSQL, MinIO (S3-compatible), Redis.
* **Doc parsing:** pdfplumber, camelot, PyMuPDF, BeautifulSoup, pandas.
* **NLP/NLU:** transformers, PyTorch, llama.cpp
* **Validation:** phonenumbers, usaddress, libpostal, dateparser.
* **Observability:** Prometheus, OpenTelemetry, Grafana.
* **DevOps:** Docker + Docker Compose (single command to spin up).

---

## Local-only, reproducible setup

> **Requirement satisfied:** *No uploads to third-party servers; no proprietary LLM APIs.*

### Prereqs

* Docker + Docker Compose
* (Optional) NVIDIA drivers for GPU
* Node 18+, Python 3.11+ if running outside Docker

### One-liner (recommended)

```bash
docker compose up --build
```

This brings up:

* `api` (FastAPI) at `http://localhost:8000`
* `web` (Next.js) at `http://localhost:3000`
* `rabbitmq`, `postgres`, `redis`, `minio`, `worker`
* (optional) `mailpit` for local SMTP testing at `http://localhost:8025`
* (optional) `grafana` at `http://localhost:3001` (Prometheus pre-wired)

### First run

1. Open `http://localhost:3000`
2. Click **Upload .eml** (or send an email to Mailpit and click **Open Inbox**)
3. Click **Process to Excel** → watch the pipeline run
4. Review flagged cells, **diff & rollback** if needed
5. Click **Export** → download your Excel (exact template)

> All artifacts (raw `.eml`, PDF pages, intermediate JSON, exports) are stored **locally** in MinIO.

---

## 🧪 Running models locally

* **SLM (our fine-tuned LoRA):** load base model + LoRA adapters from local path.
* **Ollama / llama.cpp** (optional): host small text models locally for lightweight classification.

> The repo ships with **offline model cache instructions** (weights folder or HF cache mirror) and **env toggles** to disable/enable LLM usage per job.

---

## Training (local) — **GRPO + LoRA** on SLM

1. **Install required packages**
  ```bash
   pip3 install -r training/requirements.txt
   ```

2. **Train LoRA adapters with GRPO**

   ```bash
   python training/train.py \
     --base_model "Qwen3-4B-Instruct-2507" \
     --data_dir training/dataset \
     --output_dir ./models/grpo_lora
   ```

3. **Convert trained LoRA to GGUF format using [llama.cpp](https://github.com/ggml-org/llama.cpp/blob/master/convert_lora_to_gguf.py)**

    ```bash
    python3 convert_lora_to_gguf.py --base-model-id "Qwen3-4B-Instruct-2507-GGUF" --outtype f16 --outfile ./models/adapter.gguf ./models/grpo_lora/
    ```
4. **Serve locally**

   ```bash
   docker run -d --name llama-server -p 5000:8080 -v $(pwd)/models:/models ghcr.io/ggerganov/llama.cpp:server -m /models/adapter.gguf --host 0.0.0.0 --port 8080
   ```

---

## 🧷 Data model (versioning & audit)

* `emails` – raw intake metadata + MinIO URI
* `jobs` – lifecycle/status; current\_version\_id
* `versions` – append-only snapshots (system/user edits)
* `records` – rows per version (payload\_json + confidence + method)
* `issues` – per-cell problems with severity + suggestions
* `exports` – Excel artifacts with checksum + provenance
* `audit_log` – who/what/when for every action

> Rollback ≡ set `current_version_id` to any prior version; re-export is deterministic.

---

## Analytics & Observability

* **Metrics:** throughput, latency per stage, extractor coverage, **LLM fallback rate**, validation error mix, edits per job, export counts.
* **Traces:** one trace per job across agents; instant root-cause when something slows/fails.
* **Dashboards:** pipeline SLOs, hot senders, error heatmaps, cost/time breakdowns.

---

## Edge cases we handle

* Mixed/forwarded threads; quoted text and signatures
* Multi-attachment emails (choose best candidate but keep alternates)
* Corrupt/locked PDFs (graceful fail with actionables)
* Ambiguous dates (explicit `MDY` unless sender profile overrides)
* Addresses with low parser confidence (escalate + flag)
* NPI typos (Luhn catch + fix suggestions)
* Idempotency (message-id + content checksum)

---

## Privacy & Compliance (local-only)

* All data stays on your machine (MinIO + Postgres disks).
* TLS/at-rest encryption are supported (disabled by default for local demo).
* Authentication/authorization hooks in the web app.
* Full audit trail (view/edit/export).

> Designed to align with HIPAA security safeguards when deployed in a secured environment.

---

## Project structure (overview)

```
.
├─ api/                # FastAPI app (ingest, jobs, versions, exports)
├─ workers/            # Celery tasks (multi-agent pipeline)
├─ models/             # Local base weights + LoRA adapters (no internet)
├─ services/           # slm_server.py, vlm_server.py (local inference)
├─ web/                # Next.js app (Inbox, Review, Analytics)
├─ tools/              # silver data gen, augmentation, validators
├─ training/           # GRPO trainer, reward functions, eval
├─ docker-compose.yml  # local stack
└─ README.md
```

---

## How to run (quick)

```bash
# 1) start the stack
docker compose up --build

# 2) open UI
open http://localhost:3000

# 3) upload a .eml and click "Process to Excel"
```


## Design decisions (and why)

* **Rules → then AI:** deterministic tools are fast and predictable; AI covers the weird 10–20% (PDF scans, broken tables).
* **Agents, not a monolith:** clear boundaries, easier testing, targeted retries, and future parallelism.
* **Version-everything:** healthcare ops need auditability and reversibility; versions make trust visible.
* **Local-first:** meets hackathon constraints and real-world privacy expectations; can be cloudified later with the same APIs.
* **GRPO over pure SFT:** schema compliance is about *preferences* (good vs almost-good); GRPO teaches the model what “good” *means*.

---

## Roadmap / Future scope

* Provider masterdata joins (NPPES cache, specialty codes), offline-first
* Active learning loop from operator edits → auto-label → re-train
* Multi-tenant RBAC, approvals, and branch/merge versions
* Streaming extraction for massive PDFs; multi-page parallelization
* K8s deployment with autoscaling workers & GPU pools
* Pluggable parsers (DocTR, Donut, Nougat) behind the same Agent API

---

##  How to cite / inspiration (open source)

* Qwen3-4B-Instruct-2507 (Qwen) and Qwen3-4B-Instruct-2507-GGUF (UnslothAI)
* pdfplumber, Camelot, PyMuPDF, BeautifulSoup, pandas
* phonenumbers, usaddress, libpostal, dateparser
* Celery, RabbitMQ, FastAPI, Next.js, Tailwind, Prometheus, Grafana

*(All run locally; we don’t call any proprietary APIs.)*

---

## Hackathon compliance checklist

* [x] Public repo with **full code and run script(s)**
* [x] **README** (this file), exact run instructions
* [x] **No uploads** to third-party servers; **no proprietary LLM APIs**
* [x] LLM run **locally** (weights stored locally / mounted)
* [x] Reproducible with Docker Compose on any laptop

---

## Maintainers

* Core engineering: Multi-agent design, data modeling, training, and UI/UX.
* Contact: [Parth Badgurjar](https://github.com/Parth-Badgujar) [Agam Pandey](https://github.com/AGAMPANDEYY)
