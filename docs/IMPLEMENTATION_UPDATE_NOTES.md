# Professor workspace and agent reliability update

## Professor workspace
- The professor now lands on a course overview with course cards and a Create Course form.
- Opening a course takes the professor into the existing course workspace.
- The workspace sidebar is sticky within the viewport while the main content scrolls.
- The roster shows five students initially; larger rosters can be expanded and have their own scroll area.

## Grading policy import
- Upload a CSV or XLSX policy file from the Academic Evaluation panel.
- Required columns: `assessment`, `weight`, and `max_marks` (recognized aliases include assessment name/component, weight percentage, maximum marks/out of).
- Optional columns: `pass_percentage` and `missing_marks_policy`.
- The import only fills the editable form. It does not save the policy automatically; review and click Save grading policy.
- A starter template is in `GRADING_POLICY_IMPORT_TEMPLATE.csv`.
- Marks upload format remains unchanged. Assessment columns are normalized across case, spaces, underscores, and hyphens. `*_marks` / `*_score` suffixes are removed for matching. `*_max` / `*_maximum` columns are treated as metadata and checked against the saved policy, not treated as separate assessments.

## Performance Agent / Ollama
- Ollama endpoint and model can be configured with `OLLAMA_URL` and `OLLAMA_MODEL_NAME`.
- `OLLAMA_TIMEOUT_SECONDS` defaults to 240 seconds; `OLLAMA_CONNECT_TIMEOUT_SECONDS` defaults to 10 seconds.
- The performance prompt now bounds the LLM context: last 40 interactions considered for prompt assembly, at most 20 student messages (1,200 characters each / 9,000 total) and 12 tutor messages (700 characters each / 5,000 total). The deterministic evidence check still sees the full retrieved interaction list.
- Timeout returns HTTP 504 with a useful message; inability to connect to local Ollama returns HTTP 503.

## Validation performed during packaging
- Python source syntax compilation completed successfully.
- Frontend TypeScript project build (`tsc -b`) completed successfully.
- Vite bundling could not complete in this packaging environment because the uploaded Windows `node_modules` archive did not include a Linux Rolldown native binding. Reinstall dependencies on the target machine if the same issue appears.
- Pytest could not be run in this packaging environment because `pymongo` is not installed here. Run the project tests in the project's configured virtual environment.
