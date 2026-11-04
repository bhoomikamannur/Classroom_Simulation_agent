# Test Suite Audit — project9

## Inventory

- Original archive: 120 pytest-discoverable test functions.
- Current organized suite: 132 pytest-discoverable test functions across 32 test modules.
- Added in this audit: 12 deterministic tests.
- Removed from pytest discovery: two files that contained no pytest test functions.
- Python syntax validation: all test modules and the moved manual scenario helper parse successfully.
- Runtime test execution in the audit environment: blocked at `tests/conftest.py` because `pymongo` is not installed in that environment. The full suite must be run in the project's `.venv`.

## Structural changes

- `academic/`: academic evaluation, marks, policy and assessment-column tests.
- `agents/`: deterministic agent tests and agent contracts.
- `api/`: HTTP validation and authorization tests.
- `integration/`: cross-layer trigger behaviour.
- `live/`: tests that require a real LLM, vector store or external service.
- `orchestration/`: workflow routing and orchestration.
- `rag/`: course context, chunking and vector-store isolation.
- `rules/`: deterministic teacher-alert rules.
- `services/`: longitudinal state transitions and persisted alert lifecycle.

`pytest.ini` now declares the test root, adds the repository root to `pythonpath`, and documents `live` and `integration` markers.

## Defects and weaknesses corrected

1. `tests/agents/test_end_to_end_live.py` was empty and has been removed.
2. `tests/agents/test_performance.py` was an exploratory script, not a pytest module. It instantiated the Performance Agent and executed multiple live LLM calls at module scope. It has been moved to `scripts/manual_performance_scenarios.py` and now runs only when explicitly invoked.
3. `test_performance_rag_live.py` previously called the real vector store and LLM during ordinary test collection/execution without an opt-in guard. It now requires `RUN_PERFORMANCE_LIVE=1`.
4. Two Intervention Agent scenario tests used the real LLM without being marked as live. They are now in `tests/live/` and require `RUN_INTERVENTION_LIVE=1`.
5. Existing alert lifecycle unit tests tested the decision helper, but not the persistence writes. Added tests exercise `_persist_success` and assert that an existing alert is resolved with evidence/timestamp and that a resolved alert is reopened with resolution metadata cleared.
6. Added manual/automatic trigger tests for below-threshold manual force, multi-batch drain, retryable failure stop, safety cap, automatic threshold gating, three-batch automatic bound, and periodic sweep delegation.
7. Added a Performance Agent contract test verifying that the previous concept profile is included as longitudinal context and is explicitly distinguished from new student evidence.
8. Added API authorization checks preventing student-role access and professor access to a course they do not own.

## Quality assessment of existing areas

| Area | Current strength | Remaining gap |
|---|---|---|
| Performance state transitions | Good deterministic state-transition coverage | More service-level database integration and concurrency/idempotency tests |
| Misconception alerts | Decision rules plus persistence-write tests | Real MongoDB lifecycle test including active-alert query |
| Manual/automatic triggers | Deterministic trigger contract coverage | End-to-end execution with real MongoDB and asynchronous tutor request |
| Performance Agent | Empty evidence, RAG and agent-to-agent contract coverage | More chronological multi-session examples and parser failure/retry tests |
| Intervention Agent | Confused, improving, insufficient evidence, persistent misconception and extension scenarios | Keep model-dependent cases opt-in; deterministic cases should assert full semantic output |
| RAG | Course context and vector-store course filtering | Cross-course negative retrieval test against a real isolated store |
| Academic Evaluation | Policy, calculation, normalization, marks storage, API and summary coverage | More boundary tests for configuration, upload merging, deletion and stale-summary invalidation |
| Project Analysis Agent | Strong deterministic scenario and output-validation coverage | Database/API lifecycle for approvals, scope changes, checkpoint history |
| Project Tracker | Agent analysis logic has coverage | End-to-end project workflow/API tests are not represented in this test inventory |
| Authentication/API | Content retrieval auth and performance route checks | Broader role/course/student ownership checks for Tutor, Project Tracker and Academic Evaluation |
| Orchestration | Routing, role enforcement and performance workflow | Failure propagation and side-effect/idempotency tests |

## Added test coverage

### Trigger integration

- Manual trigger drains all pending batches and passes `force=True`.
- Manual processing stops on retryable failure instead of spinning.
- Manual processing respects the maximum batch safety limit.
- Automatic trigger calls the same `process_pending_analysis` core.
- Automatic trigger does not run below the meaningful-response threshold.
- Automatic trigger remains bounded to three batches.
- Periodic sweep delegates due queues to `process_all_pending_analysis`.

### Persistence and longitudinal context

- Understanding resolves an existing persistent-misconception alert.
- Resolution records evidence and timestamp.
- A returning misconception reopens the existing alert and clears resolution metadata.
- Previous profile is passed to the Performance Agent as longitudinal context, separately from new evidence.

### API access

- Student role cannot invoke professor Performance Analysis.
- Professor cannot analyze a course they do not own.

## Remaining work before calling the architecture fully validated

The current tests use deterministic mocks/fakes for the new trigger and alert persistence contracts. They do not yet prove real MongoDB transaction/concurrency behaviour. The next validation layer should add:

1. A disposable test database or `mongomock`-backed integration suite for interaction queue, profile, evidence and alert writes.
2. Concurrent manual/automatic trigger tests against the same student-course lock.
3. Idempotent retry after persistence succeeds but interaction acknowledgement is interrupted.
4. A full Tutor chat -> background trigger -> Performance Agent -> Intervention Agent -> profile/alert flow.
5. Project Tracker API lifecycle and wider role/course authorization tests.

Do not interpret a passing mocked persistence test as proof of MongoDB deployment behaviour. Run the default suite locally, then opt into live tests only when Ollama and the intended course/vector data are available.
