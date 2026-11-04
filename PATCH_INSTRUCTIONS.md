# Test Suite Organization Patch — Apply Instructions

1. Extract this ZIP into the project root, preserving relative paths and allowing files to be added/replaced.
2. Delete the obsolete paths listed below after extraction. They were moved to the new organized directories or removed because they were empty/non-pytest scripts.
3. Do not replace any backend application files; this patch changes test organization, test configuration, test documentation and the manual exploratory script only.

## Delete these old paths

- `tests/agents/test_academic_evaluation.py`
- `tests/agents/test_academic_marks_store.py`
- `tests/agents/test_academic_policy.py`
- `tests/agents/test_assessment_column_normalization.py`
- `tests/agents/test_performance_rag_live.py`
- `tests/agents/test_project_analysis_agent_live.py`
- `tests/agents/test_performance.py`
- `tests/agents/test_end_to_end_live.py`
- `tests/agents/test_intervention.py`
- `tests/agents/test_intervention_improving.py`
- `tests/test_orchestrator.py`
- `tests/test_performance_orchestration.py`
- `tests/test_chunker.py`
- `tests/test_vector_store_course_filter.py`

## Important notes

- The old `tests/agents/test_performance.py` exploratory runner is now `scripts/manual_performance_scenarios.py`.
- The empty `tests/agents/test_end_to_end_live.py` has been removed; deterministic end-to-end trigger contracts are covered under `tests/integration/`.
- Real Ollama/ChromaDB tests are opt-in. See `tests/README.md`.
- The patch does not include a real MongoDB end-to-end test. The audit report explains the remaining integration work.
