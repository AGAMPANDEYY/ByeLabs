---
mode: 'agent'
tools: ['codebase']
description: 'Generate a minimal Hugging Face Space API for MiniCPM-V that implements /infer'
---
Create a FastAPI server exposing POST /infer (multipart file + JSON "schema").
- Load MiniCPM-V with transformers; accept PDFs/images; return {"rows":[...]} matching schema.
- Add CI to build Space; document how to set VLM_URL in .env.
- Include a small rate-limit and a health endpoint.
