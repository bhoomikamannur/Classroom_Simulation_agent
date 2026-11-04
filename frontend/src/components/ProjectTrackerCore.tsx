import { useEffect, useState } from 'react'
import { ArrowLeft, CalendarDays, CheckCircle2, ClipboardList, Download, FilePlus2, FileText, LoaderCircle, MessageSquare, Plus, RefreshCw, Upload, Users, ChevronUp, Sparkles, Pencil, Trash2 } from 'lucide-react'
import { apiFetch } from '../services/api'

type Role = 'professor' | 'student'
type FileMeta = { file_id: string; filename: string; file_type: string; file_size: number; uploaded_at: string }
type Review = { review_id: string; decision: string; feedback: string; created_at: string }
type Submission = { submission_id: string; version?: number; submission_type: string; description: string; status: string; created_at: string; file?: FileMeta; analysis?: ProjectAnalysis }
type ProjectAnalysis = { summary: string; overall_status?: string; aligned_work: string[]; additional_work: string[]; deviations: string[]; incomplete_objectives: string[]; concerns: string[]; feedback_addressed?: string[]; feedback_unresolved?: string[]; evidence_limitations: string[]; recommendations: string[]; recommendation?: string; confidence: string; created_at?: string }
type StudentInstance = { student_project_id: string; student_id: string; roll_number?: string | null; student_email?: string; status: string; proposal_status: string; submissions?: Submission[]; reviews?: Review[] }
type Milestone = { milestone_id: string; title: string; description: string; due_date: string; is_mandatory: boolean }
type CourseProject = { project_id: string; course_id: string; title: string; description: string; objectives: string[]; requirements: string[]; status: string; assigned_student_count: number; students?: StudentInstance[]; milestones?: Milestone[] }
type StudentProject = { updated_at?: string; reviews?: Review[]; submissions?: Submission[]; student_project_id: string; course_project_id: string; course_id: string; course_name: string; title: string; status: string; proposal_status: string; course_project?: { description?: string; objectives?: string[]; requirements?: string[]; brief_file?: FileMeta }; milestones?: Milestone[]; latest_submission?: Submission }

async function read<T>(response: Response): Promise<T> {
  const data = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Request failed.')
  return data as T
}

async function openProjectFile(fileId: string) {
  const popup = window.open('about:blank', '_blank')
  const response = await apiFetch(`/api/project-tracker/files/${encodeURIComponent(fileId)}`)
  if (!response.ok) { const data = await response.json().catch(() => ({})); throw new Error(typeof data.detail === 'string' ? data.detail : 'Could not open file.') }
  const blob = await response.blob()
  const url = URL.createObjectURL(blob)
  if (popup) popup.location.href = url
  else { const anchor = document.createElement('a'); anchor.href = url; anchor.download = 'project-file'; anchor.click() }
  window.setTimeout(() => URL.revokeObjectURL(url), 60_000)
}

function dateLabel(value?: string) { return value ? new Date(value).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' }) : 'Not set' }

export function ProjectTrackerCore({ courseId, role, onBack }: { courseId?: string; role: Role; onBack?: () => void }) {
  const [projects, setProjects] = useState<CourseProject[]>([])
  const [studentProjects, setStudentProjects] = useState<StudentProject[]>([])
  const [selectedProject, setSelectedProject] = useState<CourseProject | null>(null)
  const [selectedStudent, setSelectedStudent] = useState<StudentInstance | null>(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [objectives, setObjectives] = useState('')
  const [requirements, setRequirements] = useState('')
  const [briefFile, setBriefFile] = useState<File | null>(null)
  const [milestoneTitle, setMilestoneTitle] = useState('')
  const [milestoneDescription, setMilestoneDescription] = useState('')
  const [milestoneDate, setMilestoneDate] = useState('')
  const [editingMilestoneId, setEditingMilestoneId] = useState('')
  const [editMilestoneTitle, setEditMilestoneTitle] = useState('')
  const [editMilestoneDescription, setEditMilestoneDescription] = useState('')
  const [editMilestoneDate, setEditMilestoneDate] = useState('')
  const [proposalFile, setProposalFile] = useState<File | null>(null)
  const [deliverableFile, setDeliverableFile] = useState<File | null>(null)
  const [submissionDescription, setSubmissionDescription] = useState('')
  const [submissionMilestone, setSubmissionMilestone] = useState('')
  const [reviewFeedback, setReviewFeedback] = useState('')
  const [reviewDecision, setReviewDecision] = useState('approved')
  const [reviewTarget, setReviewTarget] = useState<Submission | null>(null)
  const [createExpanded, setCreateExpanded] = useState(false)
  const [analysisBusy, setAnalysisBusy] = useState('')
  const [analysisBySubmission, setAnalysisBySubmission] = useState<Record<string, ProjectAnalysis>>({})

  async function load() {
    setLoading(true); setError('')
    try {
      if (role === 'professor' && courseId) {
        const data = await read<{ projects: CourseProject[] }>(await apiFetch(`/api/project-tracker/courses/${encodeURIComponent(courseId)}/projects`))
        setProjects(data.projects)
      } else if (role === 'student') {
        const data = await read<{ projects: StudentProject[] }>(await apiFetch('/api/project-tracker/mine'))
        setStudentProjects(courseId ? data.projects.filter((item) => item.course_id === courseId) : data.projects)
      }
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not load projects.') }
    finally { setLoading(false) }
  }
  // Fetch course/student project records when the active workspace changes.
  // eslint-disable-next-line react-hooks/set-state-in-effect, react-hooks/exhaustive-deps
  useEffect(() => { void load() }, [courseId, role])

  async function createProject(event: React.FormEvent) {
    event.preventDefault(); if (!courseId || busy) return
    setBusy(true); setError(''); setNotice('')
    try {
      const data = await read<{ message: string; assigned_students: number; project: CourseProject }>(await apiFetch(`/api/project-tracker/courses/${encodeURIComponent(courseId)}/projects`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ title, description, objectives: objectives.split('\n').map((x) => x.trim()).filter(Boolean), requirements: requirements.split('\n').map((x) => x.trim()).filter(Boolean), publish: true }) }))
      let briefWarning = ''
      if (briefFile) {
        const brief = new FormData(); brief.append('file', briefFile)
        try { await read(await apiFetch(`/api/project-tracker/projects/${data.project.project_id}/brief`, { method: 'POST', body: brief })) }
        catch (uploadError) { briefWarning = ` The project was published, but the PDF upload failed: ${uploadError instanceof Error ? uploadError.message : 'unknown error'}. You can retry the PDF from the project details.` }
      }
      setTitle(''); setDescription(''); setObjectives(''); setRequirements(''); setBriefFile(null); setCreateExpanded(false)
      setNotice(`Project published and assigned to ${data.assigned_students} enrolled student${data.assigned_students === 1 ? '' : 's'}.${briefWarning}`)
      await load()
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not create course project.') }
    finally { setBusy(false) }
  }

  async function addMilestone(event: React.FormEvent) {
    event.preventDefault(); if (!selectedProject || !milestoneTitle.trim() || !milestoneDate) return
    setBusy(true); setError('')
    try {
      await read(await apiFetch(`/api/project-tracker/projects/${selectedProject.project_id}/milestones`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ title: milestoneTitle, description: milestoneDescription, due_date: new Date(`${milestoneDate}T23:59:00`).toISOString(), is_mandatory: true }) }))
      setMilestoneTitle(''); setMilestoneDescription(''); setMilestoneDate(''); setNotice('Checkpoint added for the whole class.')
      await load()
      await reloadSelectedProject(selectedProject)
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not add checkpoint.') }
    finally { setBusy(false) }
  }

  async function reloadSelectedProject(project: CourseProject) {
    const data = await read<{ project: CourseProject; students: StudentInstance[]; milestones: Milestone[] }>(await apiFetch(`/api/project-tracker/projects/${project.project_id}/students`))
    const refreshed = { ...project, students: data.students, milestones: data.milestones ?? [] }
    setSelectedProject(refreshed)
    setSelectedStudent(data.students.find((student) => student.student_project_id === selectedStudent?.student_project_id) ?? data.students[0] ?? null)
  }

  function beginEditMilestone(milestone: Milestone) {
    setEditingMilestoneId(milestone.milestone_id)
    setEditMilestoneTitle(milestone.title)
    setEditMilestoneDescription(milestone.description)
    setEditMilestoneDate(milestone.due_date.slice(0, 10))
  }

  async function saveMilestoneEdit(event: React.FormEvent) {
    event.preventDefault()
    if (!editingMilestoneId || !editMilestoneTitle.trim() || !editMilestoneDate || !selectedProject) return
    setBusy(true); setError('')
    try {
      await read(await apiFetch(`/api/project-tracker/milestones/${editingMilestoneId}`, {
        method: 'PUT', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: editMilestoneTitle.trim(), description: editMilestoneDescription, due_date: new Date(`${editMilestoneDate}T23:59:00`).toISOString() }),
      }))
      setEditingMilestoneId(''); setNotice('Checkpoint updated for the class.')
      await reloadSelectedProject(selectedProject)
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not update checkpoint.') }
    finally { setBusy(false) }
  }

  async function deleteMilestone(milestone: Milestone) {
    if (!selectedProject || !window.confirm(`Delete checkpoint “${milestone.title}”? Existing submissions will remain in the student's history.`)) return
    setBusy(true); setError('')
    try {
      await read(await apiFetch(`/api/project-tracker/milestones/${milestone.milestone_id}`, { method: 'DELETE' }))
      setNotice('Checkpoint deleted. Existing submissions and history were retained.')
      await reloadSelectedProject(selectedProject)
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not delete checkpoint.') }
    finally { setBusy(false) }
  }

  async function loadProjectStudents(project: CourseProject) {
    setBusy(true); setError('')
    try {
      const data = await read<{ project: CourseProject; students: StudentInstance[]; milestones: Milestone[] }>(await apiFetch(`/api/project-tracker/projects/${project.project_id}/students`))
      setSelectedProject({ ...project, students: data.students, milestones: data.milestones ?? [] })
      // Select the first student by default so the professor sees a workspace immediately.
      setSelectedStudent(data.students[0] ?? null)
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not load student progress.') }
    finally { setBusy(false) }
  }

  async function submitFile(kind: 'proposal' | 'progress', studentProjectId: string) {
    const file = kind === 'proposal' ? proposalFile : deliverableFile
    if (!file || busy) return
    setBusy(true); setError(''); setNotice('')
    const body = new FormData(); body.append('file', file); body.append('description', submissionDescription)
    if (kind === 'progress' && submissionMilestone) body.append('milestone_id', submissionMilestone)
    try {
      const endpoint = kind === 'proposal' ? 'proposal' : 'submissions'
      await read(await apiFetch(`/api/project-tracker/student-projects/${studentProjectId}/${endpoint}`, { method: 'POST', body }))
      if (kind === 'proposal') setProposalFile(null); else setDeliverableFile(null)
      setSubmissionDescription(''); setSubmissionMilestone(''); setNotice(kind === 'proposal' ? 'Proposal submitted to your professor.' : 'Deliverable submitted to your professor.')
      await load()
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not submit file.') }
    finally { setBusy(false) }
  }

  async function submitReview() {
    if (!reviewTarget || !reviewFeedback.trim() || busy) return
    setBusy(true); setError('')
    try {
      await read(await apiFetch(`/api/project-tracker/submissions/${reviewTarget.submission_id}/review`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ decision: reviewDecision, feedback: reviewFeedback }) }))
      setReviewTarget(null); setReviewFeedback(''); setNotice('Your review has been shared with the student.')
      if (selectedProject) await loadProjectStudents(selectedProject)
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not save review.') }
    finally { setBusy(false) }
  }

  async function runAnalysis(submission: Submission) {
    if (analysisBusy) return
    setAnalysisBusy(submission.submission_id); setError(''); setNotice('')
    try {
      const result = await read<{ analysis: ProjectAnalysis }>(await apiFetch(`/api/project-tracker/submissions/${submission.submission_id}/analysis`, { method: 'POST' }))
      setAnalysisBySubmission((current) => ({ ...current, [submission.submission_id]: result.analysis }))
      setNotice('Project Analysis Agent completed its comparison. Review the findings before making a decision.')
    } catch (e) { setError(e instanceof Error ? e.message : 'Project analysis could not be completed.') }
    finally { setAnalysisBusy('') }
  }

  const heading = role === 'professor' ? 'Course Project Tracker' : 'My Project Tracker'

  return <section className="project-tracker-page">
    <div className="project-tracker-header">
      <div><span className="panel-kicker">PROJECT WORKSPACE</span><h2>{heading}</h2><p>{role === 'professor' ? 'Publish one project to the entire enrolled class and review each student independently.' : 'View your assigned projects, submit proposals and share progress with your professor.'}</p></div>
      <div className="project-header-actions">{onBack && <button className="secondary-button" onClick={onBack}><ArrowLeft size={15}/> Back to course</button>}<button className="secondary-button" onClick={() => void load()}><RefreshCw size={15}/> Refresh</button></div>
    </div>
    {error && <div className="feedback error-feedback" role="alert">{error}</div>}
    {notice && <div className="feedback success-feedback" role="status"><CheckCircle2 size={18}/>{notice}</div>}
    {loading ? <div className="project-empty"><LoaderCircle className="spin"/> Loading project tracker…</div> : role === 'professor' ? <>
      {!selectedProject && <>
        <div className="panel project-create-launcher"><div><span className="panel-kicker">COURSE PROJECTS</span><h3>Create a project for this class</h3><p>Publish once; every enrolled student receives an individual workspace.</p></div><button type="button" className="primary-button" onClick={() => setCreateExpanded((value) => !value)}>{createExpanded ? <ChevronUp size={16}/> : <Plus size={16}/>} {createExpanded ? 'Close form' : 'Add project'}</button></div>
        {createExpanded && <form className="panel project-create-form" onSubmit={createProject}>
          <div className="panel-heading"><div><span className="panel-kicker">NEW COURSE PROJECT</span><h3>Project details</h3><p>All active students enrolled in this course will receive their own project workspace automatically.</p></div><span className="panel-heading-icon"><FilePlus2 size={22}/></span></div>
          <label>Project title<input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. AI-powered attendance system" required minLength={3}/></label>
          <label>Project description<textarea value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Describe the project, scope and expected outcome…" rows={4} required minLength={10}/></label>
          <div className="project-form-grid"><label>Objectives <small>One objective per line</small><textarea value={objectives} onChange={(e) => setObjectives(e.target.value)} placeholder={'Build authentication\nGenerate attendance reports'} rows={3}/></label><label>Requirements <small>One requirement per line</small><textarea value={requirements} onChange={(e) => setRequirements(e.target.value)} placeholder={'Use React and FastAPI\nSubmit source code and report'} rows={3}/></label></div>
          <label className="project-file-input"><FileText size={16}/>{briefFile?.name ?? 'Attach project brief PDF (optional)'}<input type="file" accept="application/pdf,.pdf" onChange={(e) => setBriefFile(e.target.files?.[0] ?? null)}/></label>
          <div className="project-publish-footer"><span><Users size={16}/> Automatically assigned to every enrolled student</span><button className="primary-button" disabled={busy || !title.trim() || description.trim().length < 10}>{busy ? <LoaderCircle className="spin" size={16}/> : <Plus size={16}/>} Publish course project</button></div>
        </form>}
        <div className="project-list-heading"><div><h3>Published course projects</h3><p>{projects.length} project{projects.length === 1 ? '' : 's'} in this course</p></div></div>
        {projects.length ? <div className="project-card-grid">{projects.map((project) => <article className="project-card" key={project.project_id}><div className="project-card-top"><span className="project-status-pill">{project.status}</span><span className="project-student-count"><Users size={14}/> {project.assigned_student_count} students</span></div><h3>{project.title}</h3><p>{project.description}</p><div className="project-card-meta">{project.objectives.length} objectives · {project.requirements.length} requirements</div><button className="primary-button" onClick={() => void loadProjectStudents(project)}>Manage project <ArrowLeft size={14}/></button></article>)}</div> : <div className="project-empty"><ClipboardList size={28}/><strong>No projects published yet</strong><span>Create a course project above to assign it to the enrolled class.</span></div>}
      </>}
      {selectedProject && <>
        <button className="secondary-button project-back-link" onClick={() => { setSelectedProject(null); setSelectedStudent(null); void load() }}><ArrowLeft size={15}/> All course projects</button>
        <div className="project-detail-title"><div><span className="panel-kicker">COURSE PROJECT</span><h3>{selectedProject.title}</h3><p>{selectedProject.description}</p><div className="project-scope-grid">{selectedProject.objectives.length > 0 && <div><strong>Objectives</strong><ul>{selectedProject.objectives.map((item, index) => <li key={index}>{item}</li>)}</ul></div>}{selectedProject.requirements.length > 0 && <div><strong>Requirements</strong><ul>{selectedProject.requirements.map((item, index) => <li key={index}>{item}</li>)}</ul></div>}</div></div><span className="project-student-count"><Users size={15}/> {selectedProject.students?.length ?? selectedProject.assigned_student_count} students</span></div>
        <form className="panel milestone-form" onSubmit={addMilestone}><div><span className="panel-kicker">CHECKPOINTS</span><h3>Add a milestone for the class</h3><p>Each student receives the same checkpoint and deadline; submissions remain individual.</p></div><div className="project-form-grid"><label>Checkpoint title<input value={milestoneTitle} onChange={(e) => setMilestoneTitle(e.target.value)} placeholder="e.g. Requirement analysis" required/></label><label>Deadline<input type="date" value={milestoneDate} onChange={(e) => setMilestoneDate(e.target.value)} required/></label></div><label>Description<textarea rows={2} value={milestoneDescription} onChange={(e) => setMilestoneDescription(e.target.value)} placeholder="Expected work or deliverables"/></label><button className="primary-button" disabled={busy || !milestoneTitle.trim() || !milestoneDate}><Plus size={15}/> Add checkpoint</button></form>
        <section className="panel project-checkpoint-list">
          <div className="panel-heading"><div><span className="panel-kicker">PUBLISHED CHECKPOINTS</span><h3>Class checkpoints</h3><p>Every enrolled student sees these checkpoints in their individual workspace.</p></div><span className="panel-heading-icon"><CalendarDays size={21}/></span></div>
          {selectedProject.milestones?.length ? selectedProject.milestones.map((milestone) => <article className="project-checkpoint-row" key={milestone.milestone_id}>
            {editingMilestoneId === milestone.milestone_id ? <form className="project-checkpoint-edit" onSubmit={saveMilestoneEdit}>
              <label>Title<input value={editMilestoneTitle} onChange={(e) => setEditMilestoneTitle(e.target.value)} required/></label>
              <label>Deadline<input type="date" value={editMilestoneDate} onChange={(e) => setEditMilestoneDate(e.target.value)} required/></label>
              <label>Description<textarea rows={2} value={editMilestoneDescription} onChange={(e) => setEditMilestoneDescription(e.target.value)}/></label>
              <div><button className="primary-button" disabled={busy}>Save changes</button><button type="button" className="secondary-button" onClick={() => setEditingMilestoneId('')}>Cancel</button></div>
            </form> : <>
              <div><strong>{milestone.title}</strong><p>{milestone.description || 'No additional instructions.'}</p><small>Due {dateLabel(milestone.due_date)}</small></div>
              <div className="project-checkpoint-actions"><button className="secondary-button" disabled={busy} onClick={() => beginEditMilestone(milestone)}><Pencil size={14}/> Edit</button><button className="secondary-button danger-button" disabled={busy} onClick={() => void deleteMilestone(milestone)}><Trash2 size={14}/> Delete</button></div>
            </>}
          </article>) : <p className="empty-materials">No checkpoints have been published yet.</p>}
        </section>
        <div className="project-student-picker panel">
          <div><span className="panel-kicker">INDIVIDUAL STUDENT WORKSPACES</span><h3>Review a student's project</h3><p>Select a student to view their proposal, submissions, AI analysis and professor feedback. No need to scroll through the entire class roster.</p></div>
          {selectedProject.students?.length ? <label className="project-student-select-label">Student
            <select value={selectedStudent?.student_project_id ?? ''} onChange={(event) => setSelectedStudent(selectedProject.students?.find((student) => student.student_project_id === event.target.value) ?? null)}>
              {selectedProject.students.map((student) => <option key={student.student_project_id} value={student.student_project_id}>{student.roll_number || student.student_email || student.student_id} — {student.proposal_status.replaceAll('_', ' ')}</option>)}
            </select>
          </label> : <p>No students were enrolled when this project was published.</p>}
          <div className="project-roster-count">{selectedProject.students?.length ?? 0} individual workspaces assigned</div>
        </div>
        {selectedStudent && <div className="panel project-review-panel"><div className="panel-heading"><div><span className="panel-kicker">STUDENT PROJECT</span><h3>{selectedStudent.roll_number || selectedStudent.student_email || selectedStudent.student_id}</h3><p>{selectedStudent.status.replaceAll('_', ' ')}</p></div></div>{selectedStudent.submissions?.length ? selectedStudent.submissions.map((submission) => <article className="project-submission-row" key={submission.submission_id}><div><strong>{submission.submission_type === 'proposal' ? 'Project proposal' : 'Progress deliverable'} · v{submission.version ?? 1}</strong><small>{submission.file?.filename} · {dateLabel(submission.created_at)}</small><p>{submission.description}</p></div><div className="project-submission-actions"><button className="secondary-button" onClick={() => submission.file && void openProjectFile(submission.file.file_id).catch((e) => setError(e.message))}><Download size={14}/> View file</button>{submission.submission_type === 'progress' && <button className="secondary-button" disabled={analysisBusy === submission.submission_id} onClick={() => void runAnalysis(submission)}>{analysisBusy === submission.submission_id ? <LoaderCircle className="spin" size={14}/> : <Sparkles size={14}/>} Analyse</button>}<button className="primary-button" onClick={() => { setReviewTarget(submission); setReviewDecision('approved'); setReviewFeedback('') }}><MessageSquare size={14}/> Review</button></div>{(analysisBySubmission[submission.submission_id] || submission.analysis) && <div className="project-agent-report"><strong><Sparkles size={15}/> Project Analysis Agent</strong>{(() => { const report = analysisBySubmission[submission.submission_id] || submission.analysis!; return <><p><b>Status: {report.overall_status?.replaceAll('_', ' ') ?? 'Needs review'}</b> · {report.summary}</p><div className="project-agent-grid">{([['Aligned work', report.aligned_work], ['Additional work', report.additional_work], ['Deviations', report.deviations], ['Incomplete objectives', report.incomplete_objectives], ['Feedback addressed', report.feedback_addressed ?? []], ['Feedback unresolved', report.feedback_unresolved ?? []], ['Potential concerns', report.concerns], ['Evidence limitations', report.evidence_limitations], ['Recommendations', report.recommendations]] as [string, string[]][]).map(([label, values]) => <div key={label}><b>{label}</b>{values?.length ? <ul>{values.map((value, index) => <li key={index}>{value}</li>)}</ul> : <small>None identified</small>}</div>)}</div><small>{report.recommendation} Confidence: {report.confidence}. AI findings are advisory and require professor review.</small></> })()}</div>}</article>) : <p>No submissions yet.</p>}{selectedStudent.reviews?.map((review) => <div className="project-review-note" key={review.review_id}><strong>{review.decision.replaceAll('_', ' ')}</strong><p>{review.feedback}</p></div>)}</div>}
      </>}
    </> : <>
      {studentProjects.length ? <div className="student-project-list">{studentProjects.map((project) => <article className="panel student-project-card" key={project.student_project_id}><div className="project-card-top"><span className="project-status-pill">{project.status.replaceAll('_', ' ')}</span><span className="project-student-count">{project.course_name}</span></div><h3>{project.title}</h3><p>{project.course_project?.description}</p>{((project.course_project?.objectives?.length ?? 0) > 0 || (project.course_project?.requirements?.length ?? 0) > 0) && <div className="project-scope-grid">{project.course_project?.objectives?.length ? <div><strong>Objectives</strong><ul>{project.course_project.objectives.map((item, index) => <li key={index}>{item}</li>)}</ul></div> : null}{project.course_project?.requirements?.length ? <div><strong>Requirements</strong><ul>{project.course_project.requirements.map((item, index) => <li key={index}>{item}</li>)}</ul></div> : null}</div>}{project.course_project?.brief_file && <button className="secondary-button" onClick={() => project.course_project?.brief_file && void openProjectFile(project.course_project.brief_file.file_id).catch((e) => setError(e.message))}><Download size={14}/> View professor's project brief</button>}<div className="project-student-meta"><span>Proposal: <strong>{project.proposal_status.replaceAll('_', ' ')}</strong></span><span>Last updated: {dateLabel(project.updated_at)}</span></div>
          {project.proposal_status !== 'approved' ? <div className="project-upload-box"><h4>Submit or revise your proposal</h4><label className="project-file-input"><FileText size={16}/>{proposalFile?.name ?? 'Choose proposal file'}<input type="file" accept=".pdf,.doc,.docx,.ppt,.pptx,.txt,.md" onChange={(e) => setProposalFile(e.target.files?.[0] ?? null)}/></label><textarea rows={2} value={submissionDescription} onChange={(e) => setSubmissionDescription(e.target.value)} placeholder="Add a note for your professor (optional)"/><button className="primary-button" disabled={!proposalFile || busy} onClick={() => void submitFile('proposal', project.student_project_id)}><Upload size={15}/> Submit proposal</button></div> : <div className="project-upload-box"><h4>Submit project progress</h4>{project.milestones?.length ? <label>Checkpoint<select value={submissionMilestone} onChange={(e) => setSubmissionMilestone(e.target.value)}><option value="">General progress update</option>{project.milestones.map((milestone) => <option key={milestone.milestone_id} value={milestone.milestone_id}>{milestone.title} · Due {dateLabel(milestone.due_date)}</option>)}</select></label> : <p>Your professor has not added checkpoints yet.</p>}<label className="project-file-input"><FilePlus2 size={16}/>{deliverableFile?.name ?? 'Choose deliverable or evidence'}<input type="file" onChange={(e) => setDeliverableFile(e.target.files?.[0] ?? null)}/></label><textarea rows={2} value={submissionDescription} onChange={(e) => setSubmissionDescription(e.target.value)} placeholder="Describe what you completed, changes made and evidence included…"/><button className="primary-button" disabled={!deliverableFile || busy} onClick={() => void submitFile('progress', project.student_project_id)}><Upload size={15}/> Submit progress</button></div>}
          {project.submissions?.length ? <div className="project-milestones"><h4><FileText size={16}/> Submission history</h4>{project.submissions.map((submission) => <div className="project-milestone-row" key={submission.submission_id}><span><strong>{submission.submission_type === 'proposal' ? 'Proposal' : 'Progress deliverable'} · v{submission.version ?? 1} · {submission.file?.filename}</strong><small>{submission.description || 'No submission note added'} · {submission.status.replaceAll('_', ' ')}</small></span><time>{dateLabel(submission.created_at)}</time></div>)}</div> : null}
          {project.submissions?.filter((submission) => submission.analysis).map((submission) => <div className="project-agent-report" key={`analysis-${submission.submission_id}`}><strong><Sparkles size={15}/> Project Analysis Agent feedback</strong><p>{submission.analysis?.summary}</p><small>Confidence: {submission.analysis?.confidence}. These are advisory findings reviewed by your professor.</small></div>)}
          {project.reviews?.length ? <div className="project-milestones"><h4><MessageSquare size={16}/> Professor feedback</h4>{project.reviews.map((review) => <div className="project-review-note" key={review.review_id}><strong>{review.decision.replaceAll('_', ' ')} · {dateLabel(review.created_at)}</strong><p>{review.feedback}</p></div>)}</div> : null}
          {project.milestones?.length ? <div className="project-milestones"><h4><CalendarDays size={16}/> Course checkpoints</h4>{project.milestones.map((milestone) => <div className="project-milestone-row" key={milestone.milestone_id}><span><strong>{milestone.title}</strong><small>{milestone.description}</small></span><time>{dateLabel(milestone.due_date)}</time></div>)}</div> : null}
        </article>)}</div> : <div className="project-empty"><ClipboardList size={30}/><strong>No course projects assigned yet</strong><span>Projects published by your professors will appear here.</span></div>}
      </>}
    {reviewTarget && <div className="project-modal-backdrop"><form className="panel project-review-modal" onSubmit={(e) => { e.preventDefault(); void submitReview() }}><div className="panel-heading"><div><span className="panel-kicker">PROFESSOR REVIEW</span><h3>Review submission</h3><p>{reviewTarget.file?.filename}</p></div><button type="button" className="secondary-button" onClick={() => setReviewTarget(null)}>Close</button></div><label>Decision<select value={reviewDecision} onChange={(e) => setReviewDecision(e.target.value)}><option value="approved">Approve</option><option value="revision_requested">Request changes</option><option value="needs_clarification">Ask for clarification</option><option value="rejected">Reject</option></select></label><label>Feedback<textarea rows={4} value={reviewFeedback} onChange={(e) => setReviewFeedback(e.target.value)} required placeholder="Explain your decision and next steps…"/></label><button className="primary-button" disabled={busy || !reviewFeedback.trim()}>Save review</button></form></div>}
  </section>
}
