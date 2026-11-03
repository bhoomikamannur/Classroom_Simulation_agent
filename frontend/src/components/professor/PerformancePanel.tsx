import { useState } from 'react'
import type { PerformanceApiResponse } from '../../types'
import { apiFetch } from '../../services/api'

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
