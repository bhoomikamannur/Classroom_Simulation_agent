# Run from the repository root after extracting the update.
# Removes only obsolete duplicate components and legacy nested feature folders.
$paths = @(
  "frontend/src/components/ProjectTracker.tsx",
  "frontend/src/components/AcademicEvaluationPanel.tsx",
  "frontend/src/components/PerformancePanel.tsx",
  "frontend/src/components/student/StudentSidebar.tsx",
  "frontend/src/components/project-tracker",
  "backend/app/agents/project_tracker"
)
foreach ($path in $paths) {
  if (Test-Path $path) {
    Remove-Item -LiteralPath $path -Recurse -Force
    Write-Host "Removed obsolete: $path"
  }
}
Write-Host "Project Tracker structure cleanup complete."
