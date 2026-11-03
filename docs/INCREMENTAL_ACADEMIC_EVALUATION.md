# Incremental academic marks and final evaluation

## Workflow

1. Professors upload CSV/XLSX marks at any time. Uploads do not require a grading policy.
2. The backend merges only the assessment columns present in the file into the persistent student/course record. Other assessments are retained.
3. A later upload for the same student and assessment updates that assessment's marks.
4. `GET /academic-evaluation/register/{course_id}` returns the course-wide marks register.
5. Professors configure or import a grading policy separately.
6. `POST /academic-evaluation/final-evaluation/{course_id}` explicitly runs evaluation and stores a snapshot of the policy and its version.
7. Incomplete students are shown as `incomplete`; pass/fail is withheld until every assessment in the saved policy has marks.
8. Students can view only their own assessment-wise marks at `GET /academic-evaluation/student/{course_id}`.

## Marks file format

A file must contain exactly one student identifier column: `student_id`, `roll_number`, `roll_no`, or `student`. Remaining columns are assessment marks. Optional maximum columns can use suffixes such as `_max` or `_maximum` (for example `Quiz_max`). Marks must be numeric and non-negative. When an optional maximum is provided, marks cannot exceed it.

Assessment headers are normalized for matching across uploads. For example `Assignment 1`, `assignment_1`, and `assignment1_marks` refer to the same assessment.

## MongoDB collections

- `academic_marks`: one document per course/student, with assessment values merged incrementally.
- `academic_final_evaluations`: immutable final evaluation snapshots, including the exact policy snapshot and policy version.
- `academic_policies`: saved policy, with incrementing `version` on updates.

## API endpoints

- `POST /academic-evaluation/upload` — incremental marks upload; no policy required.
- `GET /academic-evaluation/register/{course_id}` — professor marks register.
- `GET /academic-evaluation/student/{course_id}` — enrolled student's own marks.
- `POST /academic-evaluation/final-evaluation/{course_id}` — explicit final evaluation.
- `GET /academic-evaluation/final-evaluation/{course_id}/latest` — latest saved final evaluation.
