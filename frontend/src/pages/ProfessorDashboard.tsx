import { useEffect, useState, type RefObject } from 'react'
import { AlertCircle, ArrowLeft, ChartNoAxesCombined, CheckCircle2, ClipboardList, FileText, Files, LayoutDashboard, LibraryBig, LoaderCircle, Plus, ShieldCheck, Trash2, Upload, X, RefreshCw, UserRound } from 'lucide-react'
import { AcademicEvaluationPanel } from '../components/professor/AcademicEvaluationPanel'
import { PerformancePanel } from '../components/professor/PerformancePanel'
import { ProfessorProjectTracker } from '../components/professor-project-tracker/ProfessorProjectTracker'
import { apiFetch } from '../services/api'
import type { AuthUser, UploadResult } from '../types'

type Course = { course_id: string; name: string; description: string; enrollment_code?: string; status: string }
type DocumentItem = { document_id: string; course_id: string; filename: string; file_type: string; file_size: number; status: string; uploaded_at: string; pages_or_slides_extracted?: number; chunk_count?: number }
type EnrolledStudent = { student_id: string; roll_number?: string | null; email?: string | null; enrolled_at?: string }
type Props = {
  currentUser: AuthUser | null; onLogout: () => void; selectedFile: File | null; fileInputRef: RefObject<HTMLInputElement | null>
  uploading: boolean; uploadError: string; uploadResult: UploadResult | null; onChooseFile: (file: File | undefined) => void
  onUpload: (courseId: string) => void; onDismissError: () => void; onDismissResult: () => void
}
async function read<T>(response: Response): Promise<T> {
  const data = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Request failed.')
  return data as T
}
export function ProfessorDashboard(props: Props) {
  const { currentUser, onLogout, selectedFile, fileInputRef, uploading, uploadError, uploadResult, onChooseFile, onUpload, onDismissError, onDismissResult } = props
  const [courses, setCourses] = useState<Course[]>([])
  const [courseId, setCourseId] = useState('')
  const [courseOpen, setCourseOpen] = useState(false)
  const [courseSection, setCourseSection] = useState<'overview' | 'students' | 'materials' | 'marks' | 'performance' | 'projects'>('overview')
  const [showAllStudents, setShowAllStudents] = useState(false)
  const [documents, setDocuments] = useState<DocumentItem[]>([])
  const [students, setStudents] = useState<EnrolledStudent[]>([])
  const [courseName, setCourseName] = useState('')
  const [courseDescription, setCourseDescription] = useState('')
  const [loading, setLoading] = useState(true)
  const [savingCourse, setSavingCourse] = useState(false)
  const [deletingId, setDeletingId] = useState('')
  const [error, setError] = useState('')
  const selectedCourse = courses.find((course) => course.course_id === courseId)
  async function loadCourses() {
    setLoading(true)
    try { const data = await read<{ courses: Course[] }>(await apiFetch('/api/courses')); setCourses(data.courses) }
    catch (e) { setError(e instanceof Error ? e.message : 'Could not load courses.') }
    finally { setLoading(false) }
  }
  async function loadDocuments(id = courseId) {
    if (!id) { setDocuments([]); return }
    try { const data = await read<{ documents: DocumentItem[] }>(await apiFetch(`/api/documents/course/${encodeURIComponent(id)}`)); setDocuments(data.documents) }
    catch (e) { setError(e instanceof Error ? e.message : 'Could not load documents.') }
  }
  async function loadStudents(id = courseId) {
    if (!id) { setStudents([]); return }
    try {
      const data = await read<{ students: EnrolledStudent[] }>(await apiFetch(`/api/courses/${encodeURIComponent(id)}/students`))
      setStudents(data.students)
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not load enrolled students.') }
  }
  // Existing data-loading effects synchronize this page with authenticated API data.
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { void loadCourses() }, [])
  // eslint-disable-next-line react-hooks/set-state-in-effect, react-hooks/exhaustive-deps
  useEffect(() => { setShowAllStudents(false); void loadDocuments(courseId); void loadStudents(courseId) }, [courseId])
  // eslint-disable-next-line react-hooks/set-state-in-effect, react-hooks/exhaustive-deps
  useEffect(() => { if (uploadResult && courseId) void loadDocuments(courseId) }, [uploadResult, courseId])
  async function createCourse(event: React.FormEvent) {
    event.preventDefault(); if (!courseName.trim() || savingCourse) return
    setSavingCourse(true); setError('')
    try {
      const data = await read<{ course: Course }>(await apiFetch('/api/courses', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name: courseName.trim(), description: courseDescription.trim() }) }))
      setCourseName(''); setCourseDescription(''); await loadCourses(); setCourseId(data.course.course_id)
      window.alert(`Course created. Enrollment code: ${data.course.enrollment_code ?? 'View course details'}`)
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not create course.') }
    finally { setSavingCourse(false) }
  }
  async function deleteDocument(document: DocumentItem) {
    if (!window.confirm(`Delete “${document.filename}” and remove its indexed course content?`)) return
    setDeletingId(document.document_id); setError('')
    try { await read(await apiFetch(`/api/documents/${encodeURIComponent(document.document_id)}`, { method: 'DELETE' })); await loadDocuments() }
    catch (e) { setError(e instanceof Error ? e.message : 'Could not delete document.') }
    finally { setDeletingId('') }
  }
  if (!courseOpen) return <section className="professor-course-home">
    <header className="professor-home-header">
      <div><span className="eyebrow">TEACHER WORKSPACE</span><h1>Welcome back.</h1><p>Choose a course to open its workspace, or create a new course.</p></div>
      <button className="secondary-button" onClick={onLogout}><ArrowLeft size={15}/> Log out</button>
    </header>
    <section className="professor-create-course panel">
      <div><span className="panel-kicker">COURSE MANAGEMENT</span><h2>Create a course</h2><p>Add a course to start managing materials, students and academic progress.</p></div>
      <form className="create-course-form" onSubmit={createCourse}>
        <input value={courseName} onChange={(e) => setCourseName(e.target.value)} placeholder="Course name" aria-label="Course name" required />
        <input value={courseDescription} onChange={(e) => setCourseDescription(e.target.value)} placeholder="Short description (optional)" aria-label="Course description" />
        <button className="primary-button" disabled={savingCourse || !courseName.trim()}>{savingCourse ? <LoaderCircle className="spin" size={16}/> : <Plus size={16}/>} Create course</button>
      </form>
      {error && <div className="feedback error-feedback">{error}</div>}
    </section>
    <div className="professor-courses-heading"><div><span className="panel-kicker">YOUR COURSES</span><h2>Courses</h2></div><span>{courses.length} total</span></div>
    {loading ? <p><LoaderCircle className="spin"/> Loading courses…</p> : courses.length ? <div className="professor-course-grid">
      {courses.map((course) => <button type="button" className="professor-course-card" key={course.course_id} onClick={() => { setCourseId(course.course_id); setCourseSection('overview'); setCourseOpen(true) }}>
        <span className="course-card-icon"><LibraryBig size={23}/></span><span className="course-card-status">{course.status}</span><strong>{course.name}</strong><span className="course-card-description">{course.description || 'Open this course to manage its learning workspace.'}</span><span className="course-card-open">Open course <ArrowLeft size={14}/></span>
      </button>)}
    </div> : <div className="professor-empty-courses"><LibraryBig size={30}/><h3>No courses yet</h3><p>Create your first course using the form above.</p></div>}
  </section>

  return <section className="dashboard">
    <aside className="dashboard-sidebar">
      <div className="sidebar-heading">TEACHER PORTAL</div>
      <button className="sidebar-link" onClick={() => setCourseOpen(false)}><LayoutDashboard size={18}/> All courses</button>
      <button className={`sidebar-link ${courseSection === 'overview' ? 'active' : ''}`} onClick={() => setCourseSection('overview')}><LibraryBig size={18}/> Course overview</button>
      <button className={`sidebar-link ${courseSection === 'students' ? 'active' : ''}`} onClick={() => setCourseSection('students')}><UserRound size={18}/> Enrolled students</button>
      <button className={`sidebar-link ${courseSection === 'materials' ? 'active' : ''}`} onClick={() => setCourseSection('materials')}><Files size={18}/> Course materials</button>
      <button className={`sidebar-link ${courseSection === 'marks' ? 'active' : ''}`} onClick={() => setCourseSection('marks')}><ShieldCheck size={18}/> Academic evaluation</button>
      <button className={`sidebar-link ${courseSection === 'performance' ? 'active' : ''}`} onClick={() => setCourseSection('performance')}><ChartNoAxesCombined size={18}/> Performance analysis</button>
      <button className={`sidebar-link ${courseSection === 'projects' ? 'active' : ''}`} onClick={() => setCourseSection('projects')}><ClipboardList size={18}/> Project Tracker</button>
      <div className="sidebar-bottom"><span className="sidebar-avatar">T</span><span><strong>{currentUser?.email ?? 'Professor'}</strong><small>Professor workspace</small></span></div>
    </aside>
    <div className="dashboard-main"><div className="dashboard-top-actions"><button className="back-button" onClick={() => setCourseOpen(false)}><ArrowLeft size={15}/> All courses</button><button className="back-button" onClick={onLogout}>Log out</button></div>
      <div className="dashboard-heading"><div><span className="eyebrow">TEACHER WORKSPACE</span><h1>{selectedCourse?.name ?? "Course workspace"}</h1><p>Manage course materials, enrolled students and academic progress.</p><div className="course-code-note"><strong>Student enrollment code:</strong> {selectedCourse?.enrollment_code ?? "Unavailable"}</div></div><div className="dashboard-heading-icon"><LibraryBig size={25}/></div></div>
      {courseSection === 'overview' && <>
        <section className="panel course-overview-panel">
          <div className="panel-heading"><div><span className="panel-kicker">COURSE OVERVIEW</span><h2>{selectedCourse?.name ?? 'Course workspace'}</h2><p>{selectedCourse?.description || 'Manage this course, its enrolled students, learning resources and academic activities.'}</p></div><span className="panel-heading-icon"><LibraryBig size={22}/></span></div>
          <div className="stats-grid">
            <button type="button" className="stat-card stat-card-action" onClick={() => setCourseSection('students')}><span className="stat-icon purple"><UserRound size={20}/></span><span className="stat-label">Enrolled students</span><strong>{students.length} students</strong><small>Open course roster</small></button>
            <button type="button" className="stat-card stat-card-action" onClick={() => setCourseSection('materials')}><span className="stat-icon teal"><Files size={20}/></span><span className="stat-label">Course materials</span><strong>{documents.length} files</strong><small>Manage uploaded resources</small></button>
            <button type="button" className="stat-card stat-card-action" onClick={() => setCourseSection('performance')}><span className="stat-icon orange"><ChartNoAxesCombined size={20}/></span><span className="stat-label">Performance analysis</span><strong>Learning insights</strong><small>Review student understanding</small></button>
            <button type="button" className="stat-card stat-card-action" onClick={() => setCourseSection('projects')}><span className="stat-icon purple"><ClipboardList size={20}/></span><span className="stat-label">Project Tracker</span><strong>Course projects</strong><small>Supervise individual progress</small></button>
          </div>
        </section>
      </>}
      {courseSection === 'students' && <section className="panel course-admin-panel">
        <div className="panel-heading"><div><span className="panel-kicker">COURSE ROSTER</span><h2>Enrolled students</h2><p>Students enrolled in {selectedCourse?.name}. Project assignments use these existing enrollment records.</p></div><span className="panel-heading-icon"><ShieldCheck size={22}/></span></div>
        {!selectedCourse ? <div className="empty-materials">Select a course to view its students.</div> : students.length ? <>
          <div className={`uploaded-document-list student-roster-list ${showAllStudents ? 'expanded' : ''}`}>{(showAllStudents ? students : students.slice(0, 8)).map((student) => <article className="uploaded-document-row" key={student.student_id}><UserRound size={20}/><div className="uploaded-document-info"><strong>{student.roll_number || 'Roll number not added'}</strong><small>{student.email || 'Email unavailable'}</small></div><span className="material-status processed">Enrolled</span></article>)}</div>
          {students.length > 8 && <button type="button" className="secondary-button roster-toggle" onClick={() => setShowAllStudents((value) => !value)}>{showAllStudents ? 'Show fewer students' : `Show all ${students.length} students`}</button>}
        </> : <div className="empty-materials">No students have enrolled in this course yet.</div>}
      </section>}
      {courseSection === 'projects' && selectedCourse && <ProfessorProjectTracker courseId={courseId} />}

      {courseSection === 'materials' && <section className="panel upload-panel" id="materials"><div className="panel-heading"><div><span className="panel-kicker">KNOWLEDGE BASE</span><h2>Course materials</h2><p>Upload, review and remove materials for the selected course.</p></div><span className="panel-heading-icon"><Files size={22}/></span></div>
        {!selectedCourse ? <div className="empty-materials">Create or select a course before uploading materials.</div> : <><div className="upload-dropzone"><span className="upload-icon"><Upload size={25}/></span><h3>{selectedFile ? selectedFile.name : 'Upload course material'}</h3><p>{selectedFile ? `${(selectedFile.size / (1024 * 1024)).toFixed(2)} MB · Ready to upload` : 'Choose a PDF document or PowerPoint presentation (.pptx).'}</p><input ref={fileInputRef} className="file-input" type="file" accept=".pdf,.pptx,application/pdf,application/vnd.openxmlformats-officedocument.presentationml.presentation" onChange={(event) => onChooseFile(event.target.files?.[0])}/><div className="upload-actions"><button className="secondary-button" onClick={() => fileInputRef.current?.click()} disabled={uploading}><FileText size={16}/> Choose file</button><button className="primary-button" onClick={() => onUpload(courseId)} disabled={!selectedFile || uploading || !courseId}>{uploading ? <><LoaderCircle className="spin" size={16}/> Processing…</> : <><Upload size={16}/> Upload material</>}</button></div><small className="format-note"><ShieldCheck size={13}/> PDF and PPTX · Maximum 25 MB</small></div>
        {uploadError && <div className="feedback error-feedback" role="alert"><AlertCircle size={19}/><div><strong>Upload failed</strong><p>{uploadError}</p></div><button className="feedback-close" onClick={onDismissError} aria-label="Dismiss error"><X size={16}/></button></div>}
        {uploadResult && <div className="feedback success-feedback" role="status"><CheckCircle2 size={21}/><div className="result-content"><strong>Material processed successfully</strong><p>{uploadResult.filename}</p><div className="result-stats"><span>{uploadResult.pages_or_slides_extracted} pages/slides extracted</span><span>{uploadResult.chunk_count} chunks stored</span></div></div><button className="feedback-close" onClick={onDismissResult} aria-label="Dismiss result"><X size={16}/></button></div>}
        <div className="uploaded-documents-heading"><div><h3>Uploaded documents</h3><p>{selectedCourse.name}</p></div><button className="secondary-button" onClick={() => void loadDocuments()}><RefreshCw size={15}/> Refresh list</button></div>
        {documents.length ? <div className="uploaded-document-list">{documents.map((doc) => <article className="uploaded-document-row" key={doc.document_id}><FileText size={22}/><div className="uploaded-document-info"><strong>{doc.filename}</strong><small>{doc.file_type.toUpperCase()} · {(doc.file_size / 1024 / 1024).toFixed(2)} MB · {doc.chunk_count ?? 0} chunks · {doc.uploaded_at ? new Date(doc.uploaded_at).toLocaleDateString() : 'Date unavailable'}</small></div><span className={`material-status ${doc.status}`}>{doc.status}</span><button className="delete-document-button" onClick={() => void deleteDocument(doc)} disabled={deletingId === doc.document_id} aria-label={`Delete ${doc.filename}`} title="Delete document">{deletingId === doc.document_id ? <LoaderCircle className="spin" size={17}/> : <Trash2 size={17}/>}</button></article>)}</div> : <div className="empty-materials">No documents uploaded to this course yet.</div>}</>}
        {error && <div className="feedback error-feedback"><AlertCircle size={18}/>{error}<button className="feedback-close" onClick={() => setError('')}><X size={15}/></button></div>}
      </section>}
      {courseSection === 'marks' && <section className="panel performance-panel" id="academic-marks"><div className="panel-heading"><div><span className="panel-kicker">ACADEMIC RECORDS</span><h2>Academic marks</h2><p>Upload and maintain assessment marks. No grading policy or final evaluation is applied in this phase.</p></div><span className="panel-heading-icon"><Files size={22}/></span></div><AcademicEvaluationPanel key={courseId} courseId={courseId}/></section>}
      {courseSection === 'performance' && <section className="panel performance-panel" id="performance"><div className="panel-heading"><div><span className="panel-kicker">STUDENT SUCCESS</span><h2>Learning performance</h2><p>Review conceptual understanding from student learning interactions. Academic marks are not used here.</p></div><span className="panel-heading-icon teal-bg"><ChartNoAxesCombined size={22}/></span></div><PerformancePanel courseId={courseId}/></section>}
    </div>
  </section>
}
