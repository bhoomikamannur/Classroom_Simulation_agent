# Five-student Performance Agent seed data

This seed dataset targets the existing active course:

- Course: Introduction to Agentic AI
- Course ID: `3ce7921b-cb0f-476f-b7d4-de62fc55dd12`
- Students: `23bcs001` through `23bcs005` using the supplied internal student UUIDs.

## Scenario design

| Roll number | Intended learning pattern | Seeded substantive student responses |
|---|---|---:|
| 23bcs001 | Strong understanding | 18 |
| 23bcs002 | Persistent misconceptions | 18 |
| 23bcs003 | Partial understanding | 18 |
| 23bcs004 | Insufficient evidence | 0 (short/noise responses only) |
| 23bcs005 | Improving understanding | 18 |

Each student has three separate chat sessions. For the four evidence-bearing profiles, session 1 has exactly 10 meaningful student responses, while sessions 2 and 3 have four each. Student and tutor messages are interleaved. This deliberately makes the first threshold batch belong to one session; a subsequent manual analysis can then test whether evidence in later sessions triggers a persistent-misconception alert. Timestamps are simulated in India Standard Time on 2–3 November 2026, converted to UTC for MongoDB, and occur after the supplied enrolment time on 2 November 2026.

The script uses the same `is_meaningful_student_response` function as the live Tutor Agent. It tags every inserted document with `seed_tag`, enabling safe cleanup. It verifies the course is active and that each supplied student UUID is enrolled before writing anything.

## Run from project root (PowerShell)

First ensure `.env` contains your existing MongoDB configuration. Do not share it.

```powershell
.\.venv\Scripts\python.exe scripts\seed_performance_scenarios.py --dry-run
```

Review the preview. Expected: 18 meaningful candidate responses for 23bcs001, 002, 003 and 005 (distributed 10, 4, 4 across the three sessions); zero for 23bcs004. The exact preview is calculated using the project's current filter, not hardcoded.

Then insert:

```powershell
.\.venv\Scripts\python.exe scripts\seed_performance_scenarios.py --apply
```

The script does not call Ollama or start analysis. It creates the three sessions and interactions per student, sets `meaningful_candidate`, sets `analysis_status=pending` only for eligible student responses, and synchronizes each student's pending counter from MongoDB.

Use the professor dashboard's **Check learning activity** and **Manually analyze pending evidence** controls to exercise the normal application flow. Each analysis batch processes at most 10 pending responses. Students with 18 candidates will have two remaining after the first successful batch; run analysis again for the second batch.

## Cleanup

Only records carrying this seed's unique `seed_tag` are deleted:

```powershell
.\.venv\Scripts\python.exe scripts\seed_performance_scenarios.py --cleanup
```

The script recomputes pending counters from remaining pending records. It does not delete real chats, student records, enrolments, learning profiles, evidence, or teacher alerts. If analysis has already run, cleanup deliberately does not delete generated profiles/evidence/alerts; inspect those separately before re-seeding.

## Important test interpretation

- `meaningful_candidate` is a deterministic pre-filter, not a judgement of correctness.
- Only student (`role=user`) messages can be candidates. Tutor (`role=assistant`) messages never count as evidence.
- Candidate messages are still classified semantically by the Performance Agent. A candidate does not automatically mean the student understands the concept.
- The seed script is idempotent by refusing to run if its seed tag already exists. Run cleanup before reseeding.
- The script does not modify timestamps of existing records.
