import { useEffect, useState } from 'react'
import { ArrowLeft, ArrowRight, BookOpen, BookOpenCheck, Bot, ClipboardList, Download, Eye, FileText, LoaderCircle, Plus, RefreshCw } from 'lucide-react'
import type { AuthUser, ChatMessage, SavedTutorChat } from '../types'
import { TutorChat } from '../components/student/TutorChat'
import { StudentSidebar } from '../components/student/StudentSidebar'
import { StudentProjectTracker } from '../components/student-project-tracker/StudentProjectTracker'
import { StudentProjectWidget } from '../components/student-project-tracker/StudentProjectWidget'
import { StudentLearningPlan } from '../components/learning/StudentLearningPlan'
import { apiFetch, downloadCourseDocument, openCourseDocument } from '../services/api'

type Course = { course_id: string; name: string; description: string; professor_id: string; enrolled_at?: string }
type Material = { document_id: string; filename: string; file_type: string; file_size: number; status: string; uploaded_at: string; pages_or_slides_extracted?: number; chunk_count?: number }
type StudentMarks = { course_id: string; assessments: Record<string, { name: string; marks: number | null; maximum_marks: number | null }> }
type Props = {
  currentUser: AuthUser | null; onLogout: () => void; selectedCourseId: string; onSelectCourse: (id: string) => void
  savedChats: SavedTutorChat[]; activeChatId: string; onOpenChat: (chatId: string) => void
  chatMessages: ChatMessage[]; chatLoading: boolean; chatError: string; chatInput: string
  onStartNewChat: () => void; onChatInputChange: (value: string) => void; onSendMessage: () => void
}
async function read<T>(response: Response): Promise<T> {
  const data = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Request failed.')
  return data as T
}
export function StudentDashboard(props: Props) {
  const { currentUser, onLogout, selectedCourseId, onSelectCourse, savedChats, activeChatId, onOpenChat, chatMessages, chatLoading, chatError, chatInput, onStartNewChat, onChatInputChange, onSendMessage } = props
  const [courses, setCourses] = useState<Course[]>([])
  const [materials, setMaterials] = useState<Material[]>([])
  const [studentMarks, setStudentMarks] = useState<StudentMarks | null>(null)
  const [enrollmentCode, setEnrollmentCode] = useState('')
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [view, setView] = useState<'courses' | 'course' | 'chat' | 'projects'>('courses')
  const selectedCourse = courses.find((course) => course.course_id === selectedCourseId)
  async function loadCourses() {
    setLoading(true); setError('')
    try { const data = await read<{ courses: Course[] }>(await apiFetch('/api/courses/mine')); setCourses(data.courses) }
    catch (e) { setError(e instanceof Error ? e.message : 'Could not load courses.') }
    finally { setLoading(false) }
  }
  // Existing data-loading effects synchronize this page with authenticated API data.
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { void loadCourses() }, [])
  /* eslint-disable react-hooks/set-state-in-effect */
  useEffect(() => {
    if (!selectedCourseId) { setMaterials([]); setStudentMarks(null); return }
    let active = true
    apiFetch(`/api/documents/course/${encodeURIComponent(selectedCourseId)}`).then((r) => read<{ documents: Material[] }>(r)).then((data) => { if (active) setMaterials(data.documents) }).catch((e) => { if (active) setError(e instanceof Error ? e.message : 'Could not load course materials.') })
    apiFetch(`/api/academic-evaluation/student/${encodeURIComponent(selectedCourseId)}`).then(read<StudentMarks>).then((data) => { if (active) setStudentMarks(data) }).catch((e) => { if (active) setStudentMarks(null); if (active) setError(e instanceof Error ? e.message : 'Could not load your marks.') })
    return () => { active = false }
  }, [selectedCourseId])
  /* eslint-enable react-hooks/set-state-in-effect */
  async function joinCourse(event: React.FormEvent) {
    event.preventDefault(); if (!enrollmentCode.trim() || busy) return
    setBusy(true); setError('')
    try {
      const data = await read<{ course: Course }>(await apiFetch('/api/courses/enroll', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ enrollment_code: enrollmentCode.trim() }) }))
      setEnrollmentCode(''); await loadCourses(); onSelectCourse(data.course.course_id); setView('course')
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not join course.') }
    finally { setBusy(false) }
  }
  if (view === 'projects') return <section className="student-projects-page">
    <header className="student-home-header"><div><span className="eyebrow">STUDENT WORKSPACE</span><h1>My Projects</h1><p>Projects assigned to you across your enrolled courses.</p></div><div className="project-header-actions"><button className="secondary-button" onClick={() => setView(selectedCourse ? 'course' : 'courses')}>Back to {selectedCourse ? 'course' : 'my courses'}</button><button className="secondary-button" onClick={onLogout}>Log out</button></div></header>
    <StudentProjectTracker onBack={() => setView(selectedCourse ? 'course' : 'courses')}/>
  </section>
  if (view === 'chat' && selectedCourse) return <section className="student-dashboard student-tutor-dashboard">
    <StudentSidebar
      currentUser={currentUser}
      savedChats={savedChats}
      activeChatId={activeChatId}
      onStartNewChat={onStartNewChat}
      onOpenChat={onOpenChat}
    />
    <main className="student-chat-column student-tutor-column">
      <div className="student-tutor-toolbar">
        <button className="secondary-button course-back" onClick={() => setView('course')}><ArrowLeft size={16}/> Back to {selectedCourse.name}</button>
        <button className="secondary-button" onClick={onLogout}>Log out</button>
      </div>
      <TutorChat onLogout={onLogout} chatMessages={chatMessages} chatLoading={chatLoading} chatError={chatError} chatInput={chatInput} onStartNewChat={onStartNewChat} onChatInputChange={onChatInputChange} onSendMessage={onSendMessage}/>
    </main>
  </section>
  return <section className="student-home">
    <header className="student-home-header"><div><span className="eyebrow">STUDENT WORKSPACE</span><h1>{view === 'course' && selectedCourse ? selectedCourse.name : `Welcome${currentUser?.email ? `, ${currentUser.email.split('@')[0]}` : ''}`}</h1><p>{view === 'course' ? selectedCourse?.description || 'Your course learning space.' : 'Choose a course to continue learning.'}</p></div><div className="project-header-actions">{view === 'courses' && <button className="secondary-button" onClick={() => setView('projects')}><ClipboardList size={15}/> My Projects</button>}<button className="secondary-button" onClick={onLogout}>Log out</button></div></header>
    {error && <div className="feedback error-feedback">{error}<button className="feedback-close" onClick={() => setError('')}>×</button></div>}
    {view === 'courses' ? <>
      <div className="student-section-heading"><div><h2>My courses</h2><p>Open a course to access its resources and AI tutor.</p></div><button className="secondary-button" onClick={() => void loadCourses()}><RefreshCw size={15}/> Refresh</button></div>
      {loading ? <div className="course-loading"><LoaderCircle className="spin"/> Loading your courses…</div> : courses.length ? <div className="student-course-grid">{courses.map((course) => <button className="student-course-tile" key={course.course_id} onClick={() => { onSelectCourse(course.course_id); setView('course') }}><span className="course-tile-icon"><BookOpen size={23}/></span><strong>{course.name}</strong><span>{course.description || 'Open course workspace'}</span><small>Open course <ArrowLeft size={13}/></small></button>)}</div> : <div className="empty-courses"><BookOpenCheck size={34}/><h3>No courses yet</h3><p>Join a course using the enrollment code shared by your professor.</p></div>}
      <form className="join-course-form" onSubmit={joinCourse}><div><strong>Join a course</strong><span>Enter the enrollment code provided by your professor.</span></div><input value={enrollmentCode} onChange={(e) => setEnrollmentCode(e.target.value.toUpperCase())} placeholder="Enrollment code" aria-label="Enrollment code"/><button className="primary-button" disabled={busy || !enrollmentCode.trim()}>{busy ? <LoaderCircle className="spin" size={16}/> : <Plus size={16}/>} Join course</button></form>
    </> : selectedCourse && <>
      <button className="secondary-button course-back" onClick={() => setView('courses')}><ArrowLeft size={16}/> All courses</button>
      <StudentProjectWidget courseId={selectedCourseId} onOpen={() => setView('projects')}/>
      <section className="course-materials-panel"><StudentLearningPlan courseId={selectedCourseId}/></section>
      <section className="student-project-widget student-tutor-entry-widget" aria-label="AI Tutor">
        <div className="student-project-widget-icon student-tutor-entry-icon"><Bot size={26}/></div>
        <div className="student-project-widget-content">
          <span className="panel-kicker">YOUR AI LEARNING ASSISTANT</span>
          <h2>AI Tutor</h2>
          <p>Ask questions about course concepts, get step-by-step explanations, and work through problems with your personal AI tutor.</p>
          <div className="student-project-widget-meta"><span><Bot size={14}/> Personalized learning support</span><span><BookOpen size={14}/> Continue learning anytime</span></div>
        </div>
        <button type="button" className="primary-button student-project-widget-action" onClick={() => setView('chat')}>
          Open AI Tutor <ArrowRight size={16}/>
        </button>
      </section>
      <div className="course-feature-grid course-summary-grid">
        <article className="course-feature-card"><span className="course-feature-icon"><FileText size={22}/></span><h3>Course materials</h3><p>Lecture notes and presentations shared by your professor.</p><strong>{materials.length} resources</strong></article>
        <article className="course-feature-card"><span className="course-feature-icon"><ClipboardList size={22}/></span><h3>My academic record</h3><p>Your assessment marks for this course.</p><strong>{Object.keys(studentMarks?.assessments ?? {}).length} assessments recorded</strong></article>
      </div>
      <section className="course-materials-panel"><div className="student-section-heading"><div><h2>My academic record</h2><p>Only your own assessment marks are shown here. Missing marks are displayed as —.</p></div></div>
        {studentMarks && Object.keys(studentMarks.assessments).length ? <div className="academic-table-wrap"><table className="academic-table"><thead><tr><th>Assessment</th><th>Marks</th><th>Maximum</th></tr></thead><tbody>{Object.entries(studentMarks.assessments).map(([key, item])=><tr key={key}><td>{item.name}</td><td>{item.marks ?? '—'}</td><td>{item.maximum_marks ?? '—'}</td></tr>)}</tbody></table></div> : <p>No assessment marks have been uploaded for you yet.</p>}
      </section>
      <section className="course-materials-panel"><div className="student-section-heading"><div><h2>Learning materials</h2><p>Resources available for this course.</p></div><button className="secondary-button" onClick={() => { setMaterials([]); void apiFetch(`/api/documents/course/${encodeURIComponent(selectedCourseId)}`).then((r) => read<{documents: Material[]}>(r)).then((d) => setMaterials(d.documents)).catch((e) => setError(e.message)) }}><RefreshCw size={15}/> Refresh</button></div>
      {materials.length ? materials.map((item) => <div className="student-material-row" key={item.document_id}><FileText size={20}/><div><strong>{item.filename}</strong><small>{item.file_type.toUpperCase()} · {item.pages_or_slides_extracted ?? 0} pages/slides · {item.chunk_count ?? 0} indexed sections</small></div><span className={`material-status ${item.status}`}>{item.status}</span><button className="secondary-button" type="button" onClick={() => void openCourseDocument(item.document_id).catch((e) => setError(e instanceof Error ? e.message : 'Could not open document.'))}><Eye size={15}/> View</button><button className="secondary-button" type="button" onClick={() => void downloadCourseDocument(item.document_id, item.filename).catch((e) => setError(e instanceof Error ? e.message : 'Could not download document.'))}><Download size={15}/> Download</button></div>) : <div className="empty-materials">No course materials have been uploaded yet.</div>}</section>
    </>}
  </section>
}
