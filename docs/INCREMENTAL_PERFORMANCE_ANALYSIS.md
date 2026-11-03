# Incremental Performance Analysis

## Trigger and evidence rules

- The activity counter is scoped to `(student_id, course_id)`, not to a chat session.
- A new chat or switching between saved chats does not reset the counter.
- Only newly saved student (`user`) messages can become evidence. Tutor (`assistant`) messages are never counted as evidence.
- A deterministic pre-filter excludes short acknowledgements, greetings, ordinary questions, and short uncertainty-only messages. It does not judge whether a student's explanation is correct.
- The initial automatic trigger is 10 pending meaningful-response candidates for one student in one course.
- The Performance Agent remains responsible for semantic interpretation and course-grounded diagnosis.

## Processing lifecycle

1. `learning_interactions` stores each new candidate with `analysis_status=pending`.
2. `learning_analysis_state` tracks activity and a student-course lock.
3. The tutor API schedules a background check after a successful chat response. A ready queue is processed in batches of 10.
4. `PerformanceAgent` receives only the new student responses in that batch. It does not receive old chat history as evidence.
5. Valid concept results are stored in `interaction_evidence` and accumulated in `student_learning_profiles`.
6. A batch identifier is derived from the exact interaction IDs. This makes profile counter updates idempotent if a process stops before the source interactions are acknowledged.
7. Source interactions are marked processed only after the evidence and profile persistence succeeds.
8. A parse failure, timeout, or other processing failure leaves the source interactions pending. Automatic retries are held for five minutes; a professor can manually retry sooner.

## Learning profile and teacher alerts

- The profile stores the latest concept state and counts of analyses, understood results, partial results, and misconception results.
- Historical evidence records are retained; a later result updates the current state without deleting prior evidence.
- A persistent-misconception alert is opened when the same concept is classified as confused in separate learning sessions across analysis batches.
- A professor can inspect pending activity, last analysis time, concept trends, and open alerts in the Performance panel.
- Manual analysis can process fewer than 10 pending responses. It does not reprocess already acknowledged evidence.

## MongoDB collections added/extended

- `learning_interactions`: `meaningful_candidate`, `analysis_status`, `analysis_batch_id`, `analyzed_at`.
- `learning_analysis_state`: pending activity, lock, last status, retry cooldown, timestamps.
- `interaction_evidence`: concept-specific evidence for each batch.
- `student_learning_profiles`: accumulated concept-wise state and latest diagnosis.
- `teacher_alerts`: persistent misconception alerts for professor review.

## Operational note

FastAPI background tasks run in the API process. For a multi-worker or production deployment, move the same processing function to a durable queue/worker (for example, Celery/RQ or a managed task queue). The MongoDB lock and idempotent batch IDs protect concurrent API workers, but an in-process background task is not a durable job queue if the server shuts down mid-task.
