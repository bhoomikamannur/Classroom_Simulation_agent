import { useState } from 'react'
import type { PerformanceApiResponse } from '../../types'
import { apiFetch } from '../../services/api'

export function PerformancePanel({ courseId }: { courseId: string }) {
  const [rollNumber, setRollNumber] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState<PerformanceApiResponse | null>(null)
  async function analyzePerformance() {
    if (!courseId) { setError('Select a course first.'); return }
    if (!rollNumber.trim()) { setError('Enter the enrolled student roll number.'); return }
    setLoading(true); setError(''); setResult(null)
    try {
      const response = await apiFetch('/api/performance/intervene', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ roll_number: rollNumber.trim().toLowerCase(), course_id: courseId }) })
      const data = await response.json()
      if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Performance analysis failed.')
      setResult(data as PerformanceApiResponse)
    } catch (err) { setError(err instanceof Error ? err.message : 'Unable to connect to the Performance Agent.') }
    finally { setLoading(false) }
  }
  const diagnosis = result?.performance.diagnosis
  const intervention = result?.intervention?.intervention
  const insight = result?.intervention?.teacher_insight
  const insufficient = result?.analysis_metadata?.status === 'insufficient_evidence'
  return <section className="performance-tool">
    <div className="performance-panel-header"><div><h2>Performance & Intervention</h2><p>Analyze persisted learning interactions for a student enrolled in the selected course.</p></div></div>
    <div className="performance-form"><label>Student roll number<input value={rollNumber} onChange={(e) => setRollNumber(e.target.value)} placeholder="e.g. 23bcs000" autoCapitalize="none"/></label><button type="button" className="performance-analyze-button" onClick={() => void analyzePerformance()} disabled={loading || !courseId}>{loading ? 'Analyzing learning history…' : 'Analyze student performance'}</button></div>
    {error && <div className="feedback error-feedback">{error}</div>}
    {result && <div className="performance-result"><h3>Learning diagnosis</h3><p>{diagnosis?.overall_observation}</p>{insufficient ? <p>There is not enough student-generated learning evidence to recommend an intervention yet.</p> : <><h4>Strengths</h4><ul>{(diagnosis?.strengths ?? []).map((item, i) => <li key={i}>{item}</li>)}</ul><h4>Areas to strengthen</h4><ul>{(diagnosis?.weaknesses ?? []).map((item, i) => <li key={i}>{item}</li>)}</ul>{intervention && <><h3>Suggested intervention</h3><p><strong>Objective:</strong> {intervention.objective}</p><p>{intervention.explanation}</p><p><strong>Activity:</strong> {intervention.activity}</p><p><strong>Follow-up:</strong> {intervention.follow_up_question}</p></>}{insight && <><h3>Teacher insight</h3><p>{insight.evidence_summary}</p><p><strong>Recommended action:</strong> {insight.recommended_teaching_action}</p></>}</>}</div>}
  </section>
}
