import { useState } from 'react'
import type { PerformanceApiResponse } from '../types'
import { apiFetch } from '../services/api'

export function PerformancePanel() {
  const [studentId, setStudentId] = useState('demo-student-001')
  const [subjectId, setSubjectId] = useState('agentic-ai')
  const [studentResponses, setStudentResponses] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] =
    useState<PerformanceApiResponse | null>(null)

  async function analyzePerformance() {
    const responses = studentResponses
      .split('\n')
      .map((line) => line.trim())
      .filter(Boolean)

    if (!studentId.trim() || !subjectId.trim()) {
      setError('Enter both a student ID and a subject ID.')
      return
    }

    if (responses.length === 0) {
      setError('Enter at least one student response to analyze.')
      return
    }

    setLoading(true)
    setError('')
    setResult(null)

    try {
      const response = await apiFetch('/api/performance/intervene', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          student_id: studentId.trim(),
          subject_id: subjectId.trim(),
          interactions: responses.map((content) => ({
            role: 'user',
            content,
          })),
        }),
      })

      const data = await response.json()

      if (!response.ok) {
        throw new Error(
          typeof data.detail === 'string'
            ? data.detail
            : 'Performance analysis failed. Please try again.',
        )
      }

      setResult(data as PerformanceApiResponse)
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : 'Unable to connect to the Performance Agent.',
      )
    } finally {
      setLoading(false)
    }
  }

  const diagnosis = result?.performance.diagnosis
  const intervention = result?.intervention?.intervention
  const insight = result?.intervention?.teacher_insight

  return (
    <section className="performance-tool">
      <div className="performance-panel-header">
        <div>
          <h2>Performance & Intervention</h2>
          <p>
            Analyze student responses and generate targeted
            learning recommendations.
          </p>
        </div>
      </div>

      <div className="performance-form">
        <label>
          Student ID
          <input
            value={studentId}
            onChange={(event) => setStudentId(event.target.value)}
            placeholder="e.g. student-001"
          />
        </label>

        <label>
          Subject ID
          <input
            value={subjectId}
            onChange={(event) => setSubjectId(event.target.value)}
            placeholder="e.g. agentic-ai"
          />
        </label>

        <label className="performance-responses">
          Student responses
          <textarea
            value={studentResponses}
            onChange={(event) => setStudentResponses(event.target.value)}
            placeholder={'Enter each student response on a new line.\n\nExample:\nPlanning means remembering previous information.\nPlanning decides what actions an agent should take.'}
            rows={5}
          />
          <small>
            Enter one response per line, in conversation order.
          </small>
        </label>

        <button
          type="button"
          className="performance-analyze-button"
          onClick={analyzePerformance}
          disabled={loading}
        >
          {loading ? 'Analyzing responses…' : 'Analyze performance'}
        </button>
      </div>

      {error && (
        <div className="performance-error" role="alert">
          {error}
        </div>
      )}

      {result && (
        <div className="performance-results">
          <div className="performance-result-heading">
            <h3>Student diagnosis</h3>
            <span>
              Confidence: {diagnosis?.confidence ?? 'Not provided'}
            </span>
          </div>

          <p>
            {diagnosis?.overall_observation ||
              'No overall observation was returned.'}
          </p>

          <h4>Concepts assessed</h4>
          {diagnosis?.concepts?.length ? (
            diagnosis.concepts.map((concept, index) => (
              <article
                className="performance-concept"
                key={`${concept.concept}-${index}`}
              >
                <div className="performance-concept-heading">
                  <strong>{concept.concept}</strong>
                  <span>{concept.understanding}</span>
                </div>

                {concept.evidence?.length ? (
                  <p>
                    <strong>Evidence:</strong>{' '}
                    {concept.evidence.join(' ')}
                  </p>
                ) : null}

                {concept.misconceptions?.length ? (
                  <p>
                    <strong>Misconceptions:</strong>{' '}
                    {concept.misconceptions.join(' ')}
                  </p>
                ) : null}
              </article>
            ))
          ) : (
            <p>Not enough evidence to assess individual concepts.</p>
          )}

          <div className="performance-result-columns">
            <div>
              <h4>Strengths</h4>
              {diagnosis?.strengths?.length ? (
                <ul>
                  {diagnosis.strengths.map((item, index) => (
                    <li key={index}>{item}</li>
                  ))}
                </ul>
              ) : (
                <p>No strengths identified.</p>
              )}
            </div>

            <div>
              <h4>Areas to support</h4>
              {diagnosis?.weaknesses?.length ? (
                <ul>
                  {diagnosis.weaknesses.map((item, index) => (
                    <li key={index}>{item}</li>
                  ))}
                </ul>
              ) : (
                <p>No specific weaknesses identified.</p>
              )}
            </div>
          </div>

          {intervention && (
            <section className="intervention-result">
              <div className="performance-result-heading">
                <h3>Recommended intervention</h3>
                <span>
                  Priority: {intervention.priority ?? 'Not provided'}
                </span>
              </div>

              <h4>Objective</h4>
              <p>{intervention.objective || 'Not provided.'}</p>

              <h4>Learning activity</h4>
              <p>{intervention.activity || 'Not provided.'}</p>

              <h4>Follow-up question</h4>
              <p>
                {intervention.follow_up_question || 'Not provided.'}
              </p>

              <h4>Success criteria</h4>
              <p>{intervention.success_criteria || 'Not provided.'}</p>

              {intervention.explanation && (
                <>
                  <h4>Explanation</h4>
                  <p>{intervention.explanation}</p>
                </>
              )}
            </section>
          )}

          {insight && (
            <section className="teacher-insight">
              <h3>Teacher insights</h3>

              <h4>Observed learning state</h4>
              <p>
                {insight.observed_learning_state || 'Not provided.'}
              </p>

              <h4>Evidence summary</h4>
              <p>{insight.evidence_summary || 'Not provided.'}</p>

              <h4>Recommended teaching action</h4>
              <p>
                {insight.recommended_teaching_action || 'Not provided.'}
              </p>

              <h4>Next step</h4>
              <p>{insight.next_step || 'Not provided.'}</p>
            </section>
          )}
        </div>
      )}
    </section>
  )
}
