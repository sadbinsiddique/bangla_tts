---
name: model-backend-frontend-run
description: 'Run and validate a model with backend and frontend integration. Use for FastAPI backend startup, API health checks, TTS endpoint testing, frontend API wiring, and end-to-end verification.'
argument-hint: 'Choose scope: backend-only, frontend-only, or full-e2e'
user-invocable: true
---

# Model Backend Frontend Run

Use this skill to reliably run a model through backend APIs and verify frontend integration.

## When To Use
- You need to expose model inference through an HTTP API.
- You need frontend calls to the backend model endpoint.
- You need an end-to-end runbook to confirm model output is produced correctly.
- Backend starts but model inference fails, or frontend cannot consume the API.

## Inputs To Collect
- Backend framework and start command (example: FastAPI + uvicorn).
- Frontend framework and dev command (example: Vite/React/Next).
- Endpoint contracts: request fields, response fields, error format.
- Output expectations: file path, URL, or binary stream.

## Procedure
1. Verify environment dependencies.
Install backend runtime packages and confirm import resolution for API framework, model libs, and audio/file IO libs.

2. Start backend with model lifecycle control.
Load the model once at startup, keep it in app state, and reject inference requests with a clear `503` if model is unavailable.

3. Add health and readiness checks.
Create `/` or `/health` endpoint for service reachability and include a readiness signal that the model is loaded.

4. Validate inference endpoint contract.
Define typed request and response models, validate required fields (`text`, `save_dir` or equivalent), and return deterministic JSON.

5. Test endpoint directly before frontend.
Use `curl` or API client to call the inference endpoint and verify expected output artifact (audio file path, bytes, or URL).

6. Wire frontend to backend.
Set base API URL in frontend env config, call endpoint with JSON payload, and handle loading/error/success states.

7. Run full end-to-end check.
Trigger model inference from frontend UI, verify backend logs request handling, and confirm output is playable/downloadable.

8. Document run commands and troubleshooting.
Provide backend start command, frontend start command, sample payload, and common failure fixes.

## Decision Points
- If backend import errors occur: install missing packages in the active Python environment, then re-run checks.
- If backend is up but model fails: isolate model init from request path and test startup logs.
- If endpoint works via curl but not frontend: check CORS, API base URL, and request payload shape.
- If output path is returned but file missing: verify directory creation, write permissions, and sample rate/write function.

## Quality Checks
- Backend starts without import/type errors.
- Model loads once and inference endpoint responds within expected latency.
- Response schema is stable and documented.
- Frontend request matches backend schema exactly.
- End-to-end run from UI produces a valid output artifact.

## Definition Of Done
- Model can be invoked through backend API consistently.
- Frontend can call backend and consume model output.
- Health check, inference sample, and run commands are documented.
