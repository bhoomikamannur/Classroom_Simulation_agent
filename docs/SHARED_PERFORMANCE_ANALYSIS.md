# Shared Performance & Diagnostic Analysis

## Trigger parity

Both professor-triggered and automatic analysis call the same `process_pending_analysis` core:

- Professor `/performance/reanalyze` and `/performance/intervene` use `process_all_pending_analysis`, draining pending meaningful evidence below the automatic threshold.
- Tutor chat continues to trigger `process_pending_analysis` only when the meaningful-response threshold is reached.
- `run_periodic_analysis_sweep` is a time-based trigger entry point. Schedule `python -m backend.scripts.run_periodic_performance` every 5 minutes using Windows Task Scheduler or cron. It checks student-course queues whose last analysis is at least 30 minutes old and drains their pending evidence.

Triggers differ only in when and how much queued evidence they request. Diagnosis, state transitions, intervention generation, persistence, and alert lifecycle are shared.

## Longitudinal state

The Performance Agent receives the saved concept profile as context only; it is explicitly not treated as new student evidence. Deterministic transitions preserve the previous state when a batch has insufficient evidence. A student previously marked confused/partial must provide a convincing explanation (high-confidence evidence, multiple evidence statements, or a substantial explanation) before the current state becomes understood.

Each concept stores a `state_history` entry for every successfully applied batch, including previous/proposed/current state, evidence, timestamp, and batch ID. Existing evidence records remain intact.

## Teacher alert lifecycle

Persistent misconception alerts are retained as records:

- `open`: active alert shown in the professor's open-alert view.
- `resolved`: no longer shown as active; includes `resolved_at`, `resolution_evidence`, and `resolution_reason`.
- If the misconception appears again, the same unique student/course/concept alert is reopened and its resolution fields are cleared.

Resolved records are intentionally not physically deleted. This preserves the audit trail and avoids duplicate alerts. The existing status endpoint filters to `status: open`, so resolved alerts disappear from the active view.

## Operational notes

- Automatic chat trigger threshold remains 10 meaningful student responses, batch size remains 10.
- Manual analysis drains up to 50 batches per request (500 responses) and returns a summary of processed batches.
- Periodic sweep checks up to 100 student-course queues per invocation.
- Locking, idempotent batch IDs, and pending-on-failure behaviour remain in the core processing function.
- The periodic sweep is an executable entry point, not a continuously running in-process scheduler. Configure it in the host's scheduler.
