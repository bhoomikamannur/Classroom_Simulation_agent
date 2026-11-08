import { useEffect, useState } from 'react'
import { AlertTriangle, RefreshCw, ShieldAlert } from 'lucide-react'
import { apiFetch } from '../../services/api'

type Evidence = { course: string; issue: string; severity: string; details: string }
type AssessmentDetail = {
  assessment_key: string; assessment_name: string; student_percentage: number
  class_average_percentage: number | null; gap_from_class_average: number | null
  previous_percentage: number | null; change_from_previous: number | null
  risk_score: number; poor_performance: boolean
}
type CourseAssessmentAnalysis = {
  course_id: string; course: string; score: number; high_alert: boolean
  poor_assessment_count: number; assessed_component_count: number; assessments: AssessmentDetail[]
}
type Dimension = { score: number; available: boolean; evidence: Evidence[]; assessment_analysis?: CourseAssessmentAnalysis[] }
type StudentRisk = { student_id: string; student_name: string; roll_number?: string; risk_score: number; risk_level: string; affected_dimensions: number; affected_areas: string[]; dimensions: Record<string, Dimension>; recommended_action: string }
type Dashboard = { students: StudentRisk[]; summary: Record<string, number>; courses_analysed: number; generated_at: string; method: string }
async function read<T>(response: Response): Promise<T> { const data = await response.json().catch(() => ({})); if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Request failed.'); return data as T }
const labels: Record<string, string> = { conceptual: 'Conceptual understanding', progress: 'Learning progress', academic: 'Academic performance', project: 'Project submissions' }
export function RiskAssessmentPanel() {
  const [data, setData] = useState<Dashboard | null>(null)
  const [selected, setSelected] = useState<StudentRisk | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  async function load() { setLoading(true); setError(''); try { const result = await read<Dashboard>(await apiFetch('/api/risk-assessment/dashboard')); setData(result); setSelected((current) => current ? result.students.find((item) => item.student_id === current.student_id) ?? null : null) } catch (e) { setError(e instanceof Error ? e.message : 'Could not load risk dashboard.') } finally { setLoading(false) } }
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { void load() }, [])
  return <section className="risk-dashboard-panel">
    <div className="panel-heading"><div><span className="panel-kicker">CROSS-MODULE EARLY WARNING</span><h2>Student Risk & Intervention Centre</h2><p>Consolidated indicators across conceptual understanding, course progress, academic evaluations and project milestones.</p></div><span className="panel-heading-icon"><ShieldAlert size={22}/></span></div>
    <div className="risk-dashboard-actions"><span>Across {data?.courses_analysed ?? 0} of your courses</span><button className="secondary-button" onClick={() => void load()} disabled={loading}><RefreshCw size={14}/> {loading ? 'Refreshing…' : 'Refresh analysis'}</button></div>
    {error && <div className="feedback error-feedback">{error}</div>}
    {data && <>
      <div className="risk-summary-grid">{(['critical', 'high', 'moderate', 'low', 'insufficient_data'] as const).map((level) => <article className={`risk-summary-card risk-${level}`} key={level}><strong>{data.summary[level] ?? 0}</strong><span>{level === 'insufficient_data' ? 'insufficient data' : `${level} risk`}</span></article>)}</div>
      <div className="risk-student-layout"><div className="risk-student-list"><h3>Prioritized students</h3>{data.students.length ? data.students.map((student, index) => <button type="button" key={student.student_id} className={`risk-student-row ${selected?.student_id === student.student_id ? 'selected' : ''}`} onClick={() => setSelected(student)}><span className="risk-rank">{index + 1}</span><span className="risk-student-identity"><strong>{student.student_name}</strong><small>{student.roll_number || student.student_id.slice(0, 8)} · {student.affected_dimensions} affected areas</small></span><span className={`risk-pill risk-${student.risk_level}`}>{student.risk_score} · {student.risk_level.replaceAll('_', ' ')}</span></button>) : <p>No enrolled students found across your active courses.</p>}</div>
      <div className="risk-student-detail">{selected ? <><div className="risk-detail-heading"><div><span className="panel-kicker">STUDENT INVESTIGATION</span><h3>{selected.student_name}</h3><p>{selected.roll_number || selected.student_id}</p></div><span className={`risk-pill risk-${selected.risk_level}`}>{selected.risk_level.replaceAll('_', ' ').toUpperCase()} · {selected.risk_score}/100</span></div><p className="risk-recommendation"><AlertTriangle size={16}/>{selected.recommended_action}</p>{Object.entries(selected.dimensions).map(([key, dimension]) => <article className="risk-dimension" key={key}><div><strong>{labels[key] || key}</strong><span>{dimension.available ? `${dimension.score}/100` : 'No data'}</span></div>{dimension.available && <div className="risk-meter"><span style={{ width: `${dimension.score}%` }}/></div>}{dimension.evidence.map((item, index) => <p key={index}><b>{item.course}:</b> {item.issue} — {item.details}</p>)}{key === 'academic' && dimension.assessment_analysis?.map((course) => <div className="risk-assessment-course" key={course.course_id}><div className="risk-assessment-course-heading"><strong>{course.course}</strong><span className={course.high_alert ? 'risk-assessment-alert' : ''}>{course.high_alert ? 'Consistently low performance' : `${course.poor_assessment_count} low assessment(s)`}</span></div><div className="risk-assessment-table">{course.assessments.map((assessment) => <div className="risk-assessment-row" key={assessment.assessment_key}><strong>{assessment.assessment_name}</strong><span>{assessment.student_percentage}%</span><span>{assessment.class_average_percentage == null ? 'Class avg —' : `Class avg ${assessment.class_average_percentage}%`}</span><span>{assessment.previous_percentage == null ? 'Previous —' : `Previous ${assessment.previous_percentage}%`}</span><span>{assessment.change_from_previous == null ? '' : `${assessment.change_from_previous > 0 ? '+' : ''}${assessment.change_from_previous} pp`}</span></div>)}</div></div>)}</article>)}</> : <div className="risk-empty-detail"><ShieldAlert size={28}/><p>Select a student to inspect their consolidated risk profile and supporting evidence.</p></div>}</div></div>
      <small className="risk-method-note">{data.method} Generated {new Date(data.generated_at).toLocaleString()}.</small>
    </>}
  </section>
}
