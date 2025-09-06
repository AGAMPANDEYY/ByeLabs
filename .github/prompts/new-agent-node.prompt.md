---
mode: 'agent'
tools: ['codebase']
description: 'Add a new pipeline agent node'
---
Goal: Add a new agent in app/agents/ that follows our multi-agent pattern (class + pure function).

Requirements:
1) Create `app/agents/{{agent_slug}}.py` with:
   - clear `run(payload: dict) -> dict|list[dict]` entry point
   - logging with structlog and OTel span
   - unit tests in `tests/agents/test_{{agent_slug}}.py`
2) Wire the agent in `app/pipeline.py` preserving order:
   Classifier → Rule Extractor → VLM/LLM assist → {{AgentName}} → Normalizer → Validator
3) Add Prometheus metrics: counter `agent_runs_total{agent="{{AgentName}}"}` + histogram `agent_latency_seconds`.
4) Update `ARCHITECTURE.md` agents section and include example input/output JSON.

Constraints:
- Follow `.github/copilot-instructions.md`.
- Provide code diffs (filenames + patches).
- If you need new deps, update `api/requirements.txt` and Dockerfile.
