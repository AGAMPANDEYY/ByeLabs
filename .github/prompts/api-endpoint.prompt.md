---
mode: 'agent'
tools: ['codebase']
description: 'Add a FastAPI endpoint that triggers Celery and returns job status'
---
Task: Create POST /jobs/{id}/process that enqueues the pipeline and returns {job_id, task_id}.

Checklist:
- Route in app/main.py with Pydantic response model.
- Celery call `.delay(id)`; include traceparent in headers.
- Add unit test hitting TestClient, asserting 202 Accepted, and a fake Celery stub.
- Add metrics for request count + latency.
- Update openapi summary/description.
