# Inline Academic Evaluation

The Academic Evaluation page now derives assessment rows from the uploaded marks register.
Professors can remove irrelevant detected columns, configure each retained assessment's
weight and maximum marks, choose the pass threshold and missing-marks behavior, then
evaluate the course.

The evaluation endpoint is `POST /api/academic-evaluation/evaluate/{course_id}`.
It evaluates the persisted course marks, returns per-student weighted percentage and
pass status, and saves the validated configuration using the existing academic policy
store. This keeps the existing weighted calculation rules and student-facing marks
register intact while removing the need to configure policy in a separate UI workflow.

## Validation

- Assessment weights must total 100%.
- Each assessment maximum must be greater than zero.
- Pass percentage must be between 0 and 100.
- Missing marks default to `exclude`, which produces a provisional result when some
  assessments are absent. Professors can explicitly choose to count missing marks as zero.
- Removing an assessment from the configuration excludes it from evaluation; it does
  not delete the uploaded marks or the original upload record.

## Test

Run:

```powershell
python -m pytest tests/api/test_academic_evaluation_api.py -v
```

## Summarised evaluation

The evaluate endpoint also returns a deterministic course summary:
- student count, students with scores, complete/provisional/not-assessed counts;
- average score (including provisional scores, explicitly labelled), complete-results average;
- highest and lowest available scores;
- pass/fail counts and pass rate among complete results only;
- per-assessment average percentage, configured weight and number of students with marks.

The summary is descriptive arithmetic over stored marks, not an AI-generated explanation
or a diagnosis of student learning. It is invalidated in the UI after marks are edited,
uploaded, deleted, or configuration is changed, and is refreshed by evaluating again.
