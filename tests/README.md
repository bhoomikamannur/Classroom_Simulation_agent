# Test suite guide

Tests are grouped by the application responsibility they verify.

- `agents/`: deterministic agent behaviour and agent-to-agent contracts.
- `academic/`: academic evaluation, policy, marks storage and assessment-column normalization.
- `api/`: HTTP contracts, validation and authorization.
- `integration/`: cross-layer workflows that use controlled dependencies.
- `live/`: opt-in tests requiring real Ollama, ChromaDB or other configured services.
- `orchestration/`: workflow routing, role enforcement and orchestration.
- `rag/`: retrieval context, chunking and vector-store course isolation.
- `rules/`: deterministic teacher-alert decision rules.
- `services/`: incremental processing, state transitions, persistence and trigger contracts.

## Default test run

From the repository root, with the project virtual environment active:

```powershell
python -m pytest
```

Live tests are skipped unless their corresponding environment flag is set.

## Live tests

Performance + RAG + Ollama:

```powershell
$env:RUN_PERFORMANCE_LIVE = "1"
$env:PERFORMANCE_LIVE_COURSE_ID = "<course-id-with-indexed-material>"
python -m pytest tests/live/test_performance_rag_live.py -v
```

Project Analysis Agent + Ollama:

```powershell
$env:RUN_PROJECT_AGENT_LIVE = "1"
python -m pytest tests/live/test_project_analysis_agent_live.py -v
```

Unset flags after running:

```powershell
Remove-Item Env:RUN_INTERVENTION_LIVE -ErrorAction SilentlyContinue\nRemove-Item Env:RUN_PERFORMANCE_LIVE -ErrorAction SilentlyContinue
Remove-Item Env:PERFORMANCE_LIVE_COURSE_ID -ErrorAction SilentlyContinue
Remove-Item Env:RUN_PROJECT_AGENT_LIVE -ErrorAction SilentlyContinue
```

## Manual exploratory scenarios

`tests/agents/test_performance.py` was not a pytest module: it executed live LLM calls at module import and contained no `test_*` functions. It has been moved to:

```powershell
python -m scripts.manual_performance_scenarios
```

It is intentionally excluded from normal test discovery.

## Test quality rules

- Unit tests should be deterministic and avoid network/model/database dependencies.
- Live tests must be explicitly opt-in and marked `live`.
- Assertions should check behaviour and important side effects, not only that a result is a dictionary.
- Integration tests should verify the boundary between components.
- Do not add empty placeholder test files.
