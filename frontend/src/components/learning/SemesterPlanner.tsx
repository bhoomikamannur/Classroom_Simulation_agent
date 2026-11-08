import { useEffect, useState } from 'react'
import { CalendarDays, Clock3, RefreshCw, Sparkles, CheckCircle2, ClipboardCheck, X } from 'lucide-react'
import { apiFetch } from '../../services/api'

type Activity = { schedule_type?: string; carried_forward?: boolean; revision_required?: boolean; topic_id: string; course_id: string; course_name: string; unit_title: string; title: string; estimated_effort_hours: number; difficulty: number; coverage_status: string; mastery_score?: number | null; week: number; status: string; schedule_reason: string }
type Week = { week: number; planned_hours: number; capacity_hours: number; over_capacity: boolean; activities: Activity[] }
type CourseAllocation = { course_id: string; course_name: string; weekly_hours: number; weekly_share_percent: number; average_mastery: number | null; performance_band: string; allocation_reason: string; remaining_effort_hours: number }
type Question = { question_id: string; course_id: string; course_name: string; topic_id: string; topic_title: string; question: string; options: string[] }
type Assessment = { assessment_id: string; week: number; mode?: string; questions: Question[] }
type Plan = { weekly_available_hours: number; semester_weeks: number; current_week: number; course_count: number; topic_count: number; version: number; weeks: Week[]; course_hour_allocations: CourseAllocation[]; planning_method: string }
async function read<T>(response: Response): Promise<T> { const data = await response.json().catch(() => ({})); if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Request failed.'); return data as T }

export function SemesterPlanner({ onBack }: { onBack: () => void }) {
  const [plan, setPlan] = useState<Plan | null>(null)
  const [hours, setHours] = useState('15')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [assessment, setAssessment] = useState<Assessment | null>(null)
  const [answers, setAnswers] = useState<Record<string, number>>({})
  const [assessmentBusy, setAssessmentBusy] = useState(false)
  const [assessmentResult, setAssessmentResult] = useState<{ score: number; topic_results: { topic_title: string; score: number }[] } | null>(null)
  async function load() {
    try { const data = await read<{ plan: Plan | null }>(await apiFetch('/api/semester-planner/mine')); setPlan(data.plan); if (data.plan) setHours(String(data.plan.weekly_available_hours)); setError('') }
    catch (e) { setError(e instanceof Error ? e.message : 'Could not load semester plan.') }
  }
  // eslint-disable-next-line react-hooks/set-state-in-effect, react-hooks/exhaustive-deps
  useEffect(() => { void load() }, [])
  async function generate() {
    setBusy(true); setError(''); setMessage('')
    try { const data = await read<{ message: string; plan: Plan }>(await apiFetch('/api/semester-planner/generate', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ weekly_available_hours: Number(hours) }) })); setPlan(data.plan); setMessage(data.message) }
    catch (e) { setError(e instanceof Error ? e.message : 'Could not generate semester plan.') }
    finally { setBusy(false) }
  }
  async function updateHours() {
    setBusy(true); setError(''); setMessage('')
    try { const data = await read<{ message: string; plan: Plan }>(await apiFetch('/api/semester-planner/availability', { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ weekly_available_hours: Number(hours) }) })); setPlan(data.plan); setMessage(data.message) }
    catch (e) { setError(e instanceof Error ? e.message : 'Could not update availability.') }
    finally { setBusy(false) }
  }
  async function markComplete(topicId: string) {
    setBusy(true); setError(''); setMessage('')
    try {
      const data = await read<{ message: string; plan: Plan | null }>(await apiFetch(`/api/semester-planner/topics/${topicId}/complete`, { method: 'POST' }))
      if (data.plan) setPlan(data.plan)
      setMessage(data.message)
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not update topic progress.') }
    finally { setBusy(false) }
  }
  async function startAssessment(weekNumber: number, mode: 'regular' | 'revision' | 'extended' = 'regular') {
    setAssessmentBusy(true); setError(''); setAssessmentResult(null); setAnswers({})
    try {
      const data = await read<{ assessment: Assessment }>(await apiFetch(`/api/semester-planner/weeks/${weekNumber}/assessment?mode=${mode}`, { method: 'POST' }))
      setAssessment(data.assessment)
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not prepare weekly assessment.') }
    finally { setAssessmentBusy(false) }
  }
  async function submitAssessment() {
    if (!assessment) return
    setAssessmentBusy(true); setError('')
    try {
      const data = await read<{ score: number; topic_results: { topic_title: string; score: number }[] }>(await apiFetch(`/api/semester-planner/assessments/${assessment.assessment_id}/submit`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ answers })
      }))
      setAssessmentResult(data); setAssessment(null); await load()
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not submit weekly assessment.') }
    finally { setAssessmentBusy(false) }
  }
  return <section className="student-home">
    <header className="student-home-header"><div><span className="eyebrow">PERSONALIZED SEMESTER PLANNER</span><h1>My semester study plan</h1><p>One adaptive calendar combining topics from all your enrolled courses. Required topics count toward progress; optional early-study and revision suggestions never make you behind.</p></div><button className="secondary-button" onClick={onBack}>Back to courses</button></header>
    {error && <div className="feedback error-feedback">{error}</div>}{message && <div className="feedback success-feedback">{message}</div>}
    <section className="course-materials-panel">
      <div className="student-section-heading"><div><h2><CalendarDays size={18} style={{ display: 'inline', verticalAlign: 'middle', marginRight: 8 }}/>Weekly availability</h2><p>Tell the planner how many hours you can realistically study across all courses each week.</p></div></div>
      <div style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}><label htmlFor="weekly-hours">Available hours per week</label><input id="weekly-hours" type="number" min="1" max="80" step="0.5" value={hours} onChange={e => setHours(e.target.value)} style={{ maxWidth: 120 }}/><button className="primary-button" disabled={busy || !Number(hours) || Number(hours) < 1 || Number(hours) > 80} onClick={() => plan ? void updateHours() : void generate()}>{busy ? 'Planning…' : plan ? 'Update and reschedule' : <><Sparkles size={15}/> Generate my semester plan</>}</button><button className="secondary-button" disabled={busy} onClick={() => void load()}><RefreshCw size={15}/> Refresh</button></div>
    </section>
    {plan && <>
      <div className="course-feature-grid course-summary-grid"><article className="course-feature-card"><span className="course-feature-icon"><CalendarDays size={22}/></span><h3>{plan.course_count} courses</h3><p>Combined into one semester plan.</p></article><article className="course-feature-card"><span className="course-feature-icon"><Clock3 size={22}/></span><h3>{plan.weekly_available_hours} hours/week</h3><p>Your declared study capacity.</p></article><article className="course-feature-card"><span className="course-feature-icon"><Sparkles size={22}/></span><h3>{plan.topic_count} topics</h3><p>Across {plan.semester_weeks} planned weeks.</p></article></div>
      <section className="course-materials-panel">
        <div className="student-section-heading"><div><h2>Adaptive course-hour allocation</h2><p>Hours are redistributed using remaining syllabus effort and demonstrated topic mastery. The total stays within your declared weekly availability.</p></div></div>
        <div className="academic-table-wrap"><table className="academic-table"><thead><tr><th>Course</th><th>Hours / week</th><th>Share</th><th>Learning signal</th><th>Why this allocation?</th></tr></thead><tbody>{(plan.course_hour_allocations ?? []).map(row => <tr key={row.course_id}><td><strong>{row.course_name}</strong></td><td>{row.weekly_hours}h</td><td>{row.weekly_share_percent}%</td><td>{row.performance_band === 'needs_support' ? 'Needs support' : row.performance_band === 'strong' ? 'Strong progress' : 'Developing'}</td><td>{row.allocation_reason}</td></tr>)}</tbody></table></div>
      </section>
      <p className="muted-text">Showing the current week (Week {plan.current_week}) and upcoming weeks. Previous weeks are removed from the active calendar; unfinished required topics roll into the current week.</p>
      {plan.weeks.map(week => <section className="course-materials-panel" key={week.week}>
        <div className="student-section-heading"><div><h2>Week {week.week} {week.week === plan.current_week ? '· Current week' : ''}</h2><p>{week.planned_hours} / {week.capacity_hours} planned hours · {week.activities.length} learning activities</p></div>{week.over_capacity && <span className="material-status warning">Capacity exceeded</span>}</div>
        {week.activities.length ? <div className="academic-table-wrap"><table className="academic-table"><thead><tr><th>Course / topic</th><th>Effort</th><th>Difficulty</th><th>Learning state</th><th>Progress</th></tr></thead><tbody>{week.activities.map(activity => <tr key={activity.topic_id}><td><strong>{activity.course_name}</strong><br/><span>{activity.title}</span><small style={{ display: 'block' }}>{activity.unit_title}</small></td><td>{activity.estimated_effort_hours}h</td><td>{activity.difficulty}/5</td><td>{activity.schedule_type === 'optional' ? 'Optional early study' : activity.schedule_type === 'revision' ? 'Optional revision' : activity.schedule_type === 'extended_assessment' ? 'Extended assessment' : activity.coverage_status === 'revision_required' ? 'Revision required' : activity.coverage_status === 'mastered' ? 'Mastered' : activity.coverage_status === 'covered' ? 'Covered' : 'Not yet covered'}<small style={{display:'block'}}>{activity.carried_forward ? 'Carried forward from an earlier week; required now.' : activity.schedule_type === 'optional' ? 'Skipping this will not make you behind.' : activity.schedule_type === 'revision' ? 'Suggested reinforcement; not a syllabus deadline.' : activity.schedule_type === 'extended_assessment' ? 'Optional challenge based on strong mastery.' : 'Required this week.'}</small></td><td>{activity.coverage_status === 'mastered' || activity.coverage_status === 'covered' || activity.coverage_status === 'revision_required' ? <span className={`material-status ${activity.coverage_status === 'revision_required' ? 'warning' : 'success'}`}><CheckCircle2 size={13}/> {activity.coverage_status === 'revision_required' ? 'Covered · revise' : 'Covered'}</span> : <button className="secondary-button" disabled={busy} onClick={() => void markComplete(activity.topic_id)}><CheckCircle2 size={14}/> Mark completed</button>}</td></tr>)}</tbody></table></div> : <p>No learning activities scheduled for this week.</p>}
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap', marginTop: 14 }}>
          {week.activities.some(a => (a.schedule_type ?? 'required') === 'required' && a.coverage_status !== 'mastered') && <button className="primary-button" disabled={assessmentBusy} onClick={() => void startAssessment(week.week, 'regular')}><ClipboardCheck size={15}/> Weekly assessment</button>}
          {week.activities.some(a => a.schedule_type === 'revision' || (a.schedule_type === 'required' && a.revision_required)) && <button className="secondary-button" disabled={assessmentBusy} onClick={() => void startAssessment(week.week, 'revision')}><RefreshCw size={15}/> Revision assessment</button>}
          {week.activities.some(a => a.schedule_type === 'extended_assessment') && <button className="secondary-button" disabled={assessmentBusy} onClick={() => void startAssessment(week.week, 'extended')}><Sparkles size={15}/> Extended assessment</button>}
          <span className="muted-text">Questions use prepared topic banks and avoid previously seen questions.</span>
        </div>
      </section>)}
    </>}
    {assessmentResult && <section className="course-materials-panel">
      <h2>Weekly assessment result</h2><h3>{assessmentResult.score}%</h3>
      {assessmentResult.topic_results.map(item => <p key={item.topic_title}>{item.topic_title}: {item.score}%</p>)}
      <p className="muted-text">Your topic coverage and mastery evidence have been updated. The planner will use these results when rebuilding the remaining schedule.</p>
    </section>}
    {assessment && <div role="dialog" aria-modal="true" aria-label={`Week ${assessment.week} assessment`} style={{ position: 'fixed', inset: 0, zIndex: 1000, background: 'rgba(15,23,42,.55)', display: 'grid', placeItems: 'center', padding: 18 }}>
      <section className="course-materials-panel" style={{ width: 'min(760px, 100%)', maxHeight: '90vh', overflowY: 'auto', background: 'white' }}>
        <header className="student-section-heading"><div><span className="eyebrow">WEEKLY CHECKPOINT</span><h2>Week {assessment.week} {assessment.mode === 'revision' ? 'revision' : assessment.mode === 'extended' ? 'extended' : 'weekly'} assessment</h2><p>{assessment.questions.length} questions across your scheduled courses</p></div><button className="secondary-button" onClick={() => setAssessment(null)} aria-label="Close assessment"><X size={16}/></button></header>
        {assessment.questions.map((q, index) => <article key={q.question_id} style={{ padding: '14px 0', borderBottom: '1px solid var(--border-color, #e5e7eb)' }}>
          <small className="muted-text">{q.course_name} · {q.topic_title} · Question {index + 1}</small><p><strong>{q.question}</strong></p>
          {q.options.map((option, optionIndex) => <label key={optionIndex} style={{ display: 'flex', gap: 8, padding: 8, cursor: 'pointer' }}><input type="radio" name={q.question_id} checked={answers[q.question_id] === optionIndex} onChange={() => setAnswers(current => ({ ...current, [q.question_id]: optionIndex }))}/>{option}</label>)}
        </article>)}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, marginTop: 16 }}><span>{Object.keys(answers).length}/{assessment.questions.length} answered</span><button className="primary-button" disabled={assessmentBusy || Object.keys(answers).length !== assessment.questions.length} onClick={() => void submitAssessment()}>{assessmentBusy ? 'Submitting…' : 'Submit assessment'}</button></div>
      </section>
    </div>}
    {!plan && <section className="course-materials-panel"><h2>Ready to build your semester plan?</h2><p>The planner will combine published lesson plans from all your enrolled courses. Courses without a published lesson plan are not included yet.</p></section>}
  </section>
}
