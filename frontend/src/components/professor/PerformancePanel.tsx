import { useEffect, useState } from 'react'
import type { PerformanceApiResponse } from '../../types'
import { apiFetch } from '../../services/api'

type CourseAlert = {
  id: string
  student_id: string
  student_name: string
  roll_number?: string | null
  alert_type: string
  concept?: string
  priority: string
  message: string
  acknowledged_at?: string | null
  created_at?: string | null
}

type ActivityStatus = {
  pending_meaningful_responses: number
  analysis_threshold: number
  threshold_reached: boolean
  analysis_in_progress: boolean
  last_analyzed_at?: string | null
  last_analysis_status: string
  last_analysis_error?: string | null
  concepts: Array<{
    concept: string
    current_state: string
    analysis_count?: number
    understood_count?: number
    partial_count?: number
    misconception_count?: number
  }>
  open_teacher_alerts: Array<{
    alert_type: string
    concept: string
    priority: string
    message: string
  }>
}

export function PerformancePanel({ courseId }: { courseId: string }) {
  const [rollNumber, setRollNumber] = useState('')
  const [loading, setLoading] = useState(false)
  const [checking, setChecking] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState<PerformanceApiResponse | null>(null)
  const [activity, setActivity] = useState<ActivityStatus | null>(null)
  const [courseAlerts, setCourseAlerts] = useState<CourseAlert[]>([])
  const [alertsLoading, setAlertsLoading] = useState(false)
  const [alertError, setAlertError] = useState('')
  const [alertActionId, setAlertActionId] = useState('')

  async function loadCourseAlerts(showLoading = false) {
    if (!courseId) { setCourseAlerts([]); return }
    if (showLoading) setAlertsLoading(true)
    try {
      const query = new URLSearchParams({ course_id: courseId })
      const response = await apiFetch(`/api/performance/alerts?${query.toString()}`)
      const data = await response.json()
      if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Could not load course alerts.')
      setCourseAlerts(Array.isArray(data.alerts) ? data.alerts as CourseAlert[] : [])
      setAlertError('')
    } catch (err) {
      setAlertError(err instanceof Error ? err.message : 'Could not load course alerts.')
    } finally {
      if (showLoading) setAlertsLoading(false)
    }
  }

  useEffect(() => {
    void loadCourseAlerts(true)
    const intervalId = window.setInterval(() => { void loadCourseAlerts() }, 30000)
    return () => window.clearInterval(intervalId)
  }, [courseId])

  async function updateCourseAlert(alert: CourseAlert, action: 'acknowledge' | 'close') {
    if (action === 'close' && !window.confirm(`Close this alert for ${alert.student_name}${alert.roll_number ? ` (${alert.roll_number})` : ''}? It will leave the active list, but its history will be retained.`)) return
    setAlertActionId(`${alert.id}:${action}`)
    setAlertError('')
    try {
      const query = new URLSearchParams({ course_id: courseId })
      const response = await apiFetch(`/api/performance/alerts/${alert.id}/${action}?${query.toString()}`, { method: 'POST' })
      const data = await response.json()
      if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : `Could not ${action} alert.`)
      await loadCourseAlerts()
    } catch (err) {
      setAlertError(err instanceof Error ? err.message : `Could not ${action} alert.`)
    } finally {
      setAlertActionId('')
    }
  }

  async function loadStatus() {
    if (!courseId || !rollNumber.trim()) {
      setError('Enter an enrolled student roll number and select a course.')
      return
    }
    setChecking(true)
    setError('')
    try {
      const query = new URLSearchParams({ roll_number: rollNumber.trim().toLowerCase(), course_id: courseId })
      const response = await apiFetch(`/api/performance/status?${query.toString()}`)
      const data = await response.json()
      if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Could not load learning activity.')
      setActivity(data as ActivityStatus)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load learning activity.')
    } finally {
      setChecking(false)
    }
  }

  async function analyzePerformance(manual = false) {
    if (!courseId) { setError('Select a course first.'); return }
    if (!rollNumber.trim()) { setError('Enter the enrolled student roll number.'); return }
    setLoading(true)
    setError('')
    setResult(null)
    try {
      const response = await apiFetch(`/api/performance/${manual ? 'reanalyze' : 'intervene'}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(manual
          ? { roll_number: rollNumber.trim().toLowerCase(), course_id: courseId }
          : { roll_number: rollNumber.trim().toLowerCase(), course_id: courseId }),
      })
      const data = await response.json()
      if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Performance analysis failed.')
      if (manual && data.status === 'failed_retry_pending') throw new Error(data.error || 'Analysis failed. Evidence remains pending for retry.')
      if (manual && !['completed', 'insufficient_evidence'].includes(data.status)) throw new Error(data.status === 'no_pending_evidence' ? 'There are no pending meaningful responses to analyze.' : `Analysis status: ${data.status}`)
      if (manual) {
        setResult(data as PerformanceApiResponse)
      } else {
        setResult(data as PerformanceApiResponse)
      }
      await loadStatus()
    } catch (err) {
      setResult(null)
      setError(err instanceof Error ? err.message : 'Unable to connect to the Performance Agent.')
    } finally {
      setLoading(false)
    }
  }

  const diagnosis = result?.performance?.diagnosis
  const intervention = result?.intervention?.intervention
  const insight = result?.intervention?.teacher_insight
  const lastAnalyzed = activity?.last_analyzed_at
    ? new Date(activity.last_analyzed_at).toLocaleString()
    : 'Not analysed yet'

  return <section className="performance-tool">
    <div className="performance-panel-header">
      <div>
        <h2>Performance & Intervention</h2>
        <p>Monitor new learning activity and review incremental, course-specific diagnoses.</p>
      </div>
    </div>
    <div className="performance-form">
      <label>Student roll number
        <input value={rollNumber} onChange={(e) => { setRollNumber(e.target.value); setActivity(null); setResult(null) }} placeholder="e.g. 23bcs000" autoCapitalize="none" />
      </label>
      <div className="performance-actions">
        <button type="button" className="performance-analyze-button" onClick={() => void loadStatus()} disabled={checking || !courseId}>
          {checking ? 'Checking activity…' : 'Check learning activity'}
        </button>
        <button type="button" className="performance-analyze-button" onClick={() => void analyzePerformance(true)} disabled={loading || !courseId}>
          {loading ? 'Analyzing new evidence…' : 'Manually analyze pending evidence'}
        </button>
      </div>
    </div>
    {error && <div className="feedback error-feedback" role="alert">{error}</div>}

    <div className="course-alerts-section">
      <div className="course-alerts-heading">
        <div>
          <h3>Course-wide teacher alerts</h3>
          <p>Active alerts for enrolled students. This list refreshes automatically every 30 seconds.</p>
        </div>
        <span className="course-alert-count">{courseAlerts.length} active</span>
      </div>
      {alertError && <div className="feedback error-feedback" role="alert">{alertError}</div>}
      {alertsLoading && courseAlerts.length === 0
        ? <p>Loading course alerts…</p>
        : courseAlerts.length === 0
          ? <p className="course-alert-empty">No active alerts for this course.</p>
          : <div className="course-alert-list">
            {courseAlerts.map((alert) => <article className={`course-alert-card priority-${alert.priority.toLowerCase()}`} key={alert.id}>
              <div className="course-alert-card-top">
                <div>
                  <span className={`course-alert-priority priority-${alert.priority.toLowerCase()}`}>{alert.priority.toUpperCase()} PRIORITY</span>
                  <h4>{alert.concept || alert.alert_type.replaceAll('_', ' ')}</h4>
                  <p className="course-alert-student"><strong>{alert.student_name}</strong>{alert.roll_number ? ` · ${alert.roll_number}` : ''}</p>
                </div>
                <span className="course-alert-type">{alert.alert_type.replaceAll('_', ' ')}</span>
              </div>
              <p>{alert.message}</p>
              {alert.acknowledged_at && <small className="course-alert-acknowledged">Acknowledged · {new Date(alert.acknowledged_at).toLocaleString()}</small>}
              <div className="course-alert-actions">
                {!alert.acknowledged_at && <button type="button" onClick={() => void updateCourseAlert(alert, 'acknowledge')} disabled={!!alertActionId}>
                  {alertActionId === `${alert.id}:acknowledge` ? 'Acknowledging…' : 'Acknowledge'}
                </button>}
                <button type="button" className="course-alert-close" onClick={() => void updateCourseAlert(alert, 'close')} disabled={!!alertActionId}>
                  {alertActionId === `${alert.id}:close` ? 'Closing…' : 'Close alert'}
                </button>
              </div>
            </article>)}
          </div>}
    </div>

    {activity && <div className="performance-result">
      <h3>Incremental learning activity</h3>
      <p><strong>Pending meaningful responses:</strong> {activity.pending_meaningful_responses} / {activity.analysis_threshold}</p>
      <p><strong>Last analysed:</strong> {lastAnalyzed}</p>
      <p><strong>Status:</strong> {activity.analysis_in_progress ? 'Analysis in progress' : activity.last_analysis_status.replaceAll('_', ' ')}</p>
      {activity.last_analysis_error && <p role="alert"><strong>Last attempt:</strong> {activity.last_analysis_error}</p>}
      {activity.concepts.length > 0 && <>
        <h4>Current concept profile</h4>
        <ul>{activity.concepts.map((concept) => <li key={concept.concept}>
          <strong>{concept.concept}:</strong> {concept.current_state}
          {' '}(analyses: {concept.analysis_count ?? 0}; understood: {concept.understood_count ?? 0}; partial: {concept.partial_count ?? 0}; misconception: {concept.misconception_count ?? 0})
        </li>)}</ul>
      </>}
      {activity.open_teacher_alerts?.length > 0 && <>
        <h4>Teacher alerts</h4>
        <ul>{activity.open_teacher_alerts.map((alert, index) => <li key={`${alert.alert_type}-${alert.concept}-${index}`}>
          <strong>{alert.priority.toUpperCase()} — {alert.concept}:</strong> {alert.message}
        </li>)}</ul>
      </>}
    </div>}

    {result && <div className="performance-result">
      <h3>Latest batch diagnosis</h3>
      <p>{diagnosis?.overall_observation}</p>
      <h4>Strengths</h4>
      <ul>{(diagnosis?.strengths ?? []).map((item, i) => <li key={i}>{item}</li>)}</ul>
      <h4>Areas to strengthen</h4>
      <ul>{(diagnosis?.weaknesses ?? []).map((item, i) => <li key={i}>{item}</li>)}</ul>
      {intervention && <>
        <h3>Suggested intervention</h3>
        <p><strong>Objective:</strong> {intervention.objective}</p>
        <p>{intervention.explanation}</p>
        <p><strong>Activity:</strong> {intervention.activity}</p>
        <p><strong>Follow-up:</strong> {intervention.follow_up_question}</p>
      </>}
      {insight && <>
        <h3>Teacher insight</h3>
        <p>{insight.evidence_summary}</p>
        <p><strong>Recommended action:</strong> {insight.recommended_teaching_action}</p>
      </>}
    </div>}
  </section>
}
