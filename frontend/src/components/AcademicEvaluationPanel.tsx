import { useState } from 'react'
import { AlertCircle, FileText, Plus, X } from 'lucide-react'
import type { AcademicAssessment, AcademicEvaluationResponse, ClassAnalyticsResponse } from '../types'
import { apiFetch } from '../services/api'

export function AcademicEvaluationPanel() {
  const [courseId, setCourseId] = useState('agentic-ai')
  const [assessments, setAssessments] = useState<AcademicAssessment[]>([
    { name: '', weight: '', maximum: '' },
    { name: '', weight: '', maximum: '' },
  ])
  const [passPercentage, setPassPercentage] = useState('40')
  const [missingPolicy, setMissingPolicy] =
    useState<'exclude' | 'zero'>('exclude')
  const [policyMessage, setPolicyMessage] = useState('')
  const [policyLoading, setPolicyLoading] = useState(false)

  const [marksFile, setMarksFile] = useState<File | null>(null)
  const [evaluation, setEvaluation] =
    useState<AcademicEvaluationResponse | null>(null)
  
  const [analytics, setAnalytics] =
    useState<ClassAnalyticsResponse | null>(null)
  const [analyticsLoading, setAnalyticsLoading] = useState(false)
  const [analyticsError, setAnalyticsError] = useState('')
  const [selectedAnalyticsStudent, setSelectedAnalyticsStudent] =
    useState('')

  const [selectedStudentId, setSelectedStudentId] = useState('')
  const [uploadLoading, setUploadLoading] = useState(false)
  const [error, setError] = useState('')

  function updateAssessment(
    index: number,
    field: keyof AcademicAssessment,
    value: string,
  ) {
    setAssessments((previous) =>
      previous.map((assessment, i) =>
        i === index ? { ...assessment, [field]: value } : assessment,
      ),
    )
  }

  async function savePolicy() {
    const id = courseId.trim()

    if (!id) {
      setError('Enter a course ID.')
      return
    }

    const names = assessments.map((a) => a.name.trim())
    const weights = assessments.map((a) => Number(a.weight))
    const maximums = assessments.map((a) => Number(a.maximum))
    const pass = Number(passPercentage)

    if (
      assessments.some(
        (a) => !a.name.trim() || !a.weight.trim() || !a.maximum.trim(),
      )
    ) {
      setError('Complete the name, weight, and maximum marks for every assessment.')
      return
    }

    if (new Set(names).size !== names.length) {
      setError('Assessment names must be unique.')
      return
    }

    if (
      weights.some((w) => !Number.isFinite(w) || w <= 0 || w > 100) ||
      Math.abs(weights.reduce((sum, w) => sum + w, 0) - 100) > 0.000001
    ) {
      setError('Assessment weights must be positive and total exactly 100%.')
      return
    }

    if (maximums.some((m) => !Number.isFinite(m) || m <= 0)) {
      setError('Maximum marks must be greater than zero for every assessment.')
      return
    }

    if (!Number.isFinite(pass) || pass < 0 || pass > 100) {
      setError('Pass percentage must be between 0 and 100.')
      return
    }

    const policy = {
      course_id: id,
      assessment_weights: Object.fromEntries(
        names.map((name, i) => [name, weights[i]]),
      ),
      assessment_max_marks: Object.fromEntries(
        names.map((name, i) => [name, maximums[i]]),
      ),
      pass_percentage: pass,
      missing_marks_policy: missingPolicy,
    }

    setPolicyLoading(true)
    setError('')
    setPolicyMessage('')
    setEvaluation(null)

    try {
      const url = `/api/academic-policies/${encodeURIComponent(id)}`
      const existing = await apiFetch(url)

      let response: Response

      if (existing.ok) {
        response = await apiFetch(url, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            assessment_weights: policy.assessment_weights,
            assessment_max_marks: policy.assessment_max_marks,
            pass_percentage: policy.pass_percentage,
            missing_marks_policy: policy.missing_marks_policy,
          }),
        })
      } else if (existing.status === 404) {
        response = await apiFetch('/api/academic-policies', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(policy),
        })
      } else {
        const data = await existing.json().catch(() => ({}))
        throw new Error(data.detail || 'Could not check the existing policy.')
      }

      const data = await response.json().catch(() => ({}))

      if (!response.ok) {
        throw new Error(data.detail || 'Could not save the grading policy.')
      }

      setPolicyMessage(`Grading policy saved for course "${id}".`)
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Could not save the grading policy.',
      )
    } finally {
      setPolicyLoading(false)
    }
  }

  async function uploadMarks() {
    if (!courseId.trim()) {
      setError('Enter the course ID.')
      return
    }

    if (!marksFile) {
      setError('Choose a CSV or XLSX marks file first.')
      return
    }

    if (!/\.(csv|xlsx)$/i.test(marksFile.name)) {
      setError('Only CSV and XLSX files are supported.')
      return
    }

    setUploadLoading(true)
    setError('')
    setEvaluation(null)
    setSelectedStudentId('')

    const formData = new FormData()
    formData.append('course_id', courseId.trim())
    formData.append('file', marksFile)

    try {
      const response = await apiFetch('/api/academic-evaluation/upload', {
        method: 'POST',
        body: formData,
      })

      const data = await response.json()

      if (!response.ok) {
        throw new Error(
          typeof data.detail === 'string'
            ? data.detail
            : 'Marks evaluation failed.',
        )
      }

      const result = data as AcademicEvaluationResponse
      setEvaluation(result)

      if (result.student_results.length > 0) {
        setSelectedStudentId(result.student_results[0].student_id)
      }
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Could not evaluate the marks file.',
      )
    } finally {
      setUploadLoading(false)
    }
  }

  async function analyzeClass() {
    if (!courseId.trim()) {
      setAnalyticsError('Enter the course ID.')
      return
    }

    if (!marksFile) {
      setAnalyticsError('Choose a CSV or XLSX file first.')
      return
    }

    setAnalyticsLoading(true)
    setAnalyticsError('')
    setAnalytics(null)

    const formData = new FormData()
    formData.append('course_id', courseId.trim())
    formData.append('file', marksFile)

    try {
      const response = await apiFetch('/api/academic-evaluation/analyze', {
        method: 'POST',
        body: formData,
      })

      const data = await response.json()

      if (!response.ok) {
        throw new Error(
          typeof data.detail === 'string'
            ? data.detail
            : 'Class analytics failed.',
        )
      }

      const result = data as ClassAnalyticsResponse
      setAnalytics(result)

      if (result.student_summaries.length > 0) {
        setSelectedAnalyticsStudent(result.student_summaries[0].student_id)
      }
    } catch (err) {
      setAnalyticsError(
        err instanceof Error ? err.message : 'Could not analyze class performance.',
      )
    } finally {
      setAnalyticsLoading(false)
    }
  }

  const selectedAnalyticsRecord = analytics?.student_summaries.find(
    (student) => student.student_id === selectedAnalyticsStudent,
  )

  const lowerPerformanceCount =
    analytics?.student_summaries.filter(
      (student) => student.relative_performance === 'lower_performance_group',
    ).length ?? 0

  const studentsWithMissingMarks =
    analytics?.student_summaries.filter((student) =>
      Object.values(student.assessments).some((assessment) => assessment.marks === null),
    ).length ?? 0

  const analyticsAverageValues =
    analytics?.student_summaries
      .map((student) => student.descriptive_average_percentage)
      .filter((score): score is number => score !== null) ?? []

  const descriptiveClassAverage =
    analyticsAverageValues.length > 0
      ? analyticsAverageValues.reduce((sum, score) => sum + score, 0) /
        analyticsAverageValues.length
      : null


  const selectedStudent = evaluation?.student_results.find(
    (student) => student.student_id === selectedStudentId,
  )

  const passCount =
    evaluation?.student_results.filter((s) => s.pass_status === 'pass').length ?? 0

  const failCount =
    evaluation?.student_results.filter((s) => s.pass_status === 'fail').length ?? 0

  const assessedScores =
    evaluation?.student_results
      .map((s) => s.weighted_percentage)
      .filter((score): score is number => score !== null) ?? []

  const classAverage =
    assessedScores.length > 0
      ? assessedScores.reduce((sum, score) => sum + score, 0) /
        assessedScores.length
      : null

  return (
    <div className="academic-evaluation">
      <section className="academic-card">
        <div className="academic-section-heading">
          <div>
            <h3>Grading policy</h3>
            <p>Configure the assessment scheme used to calculate official results.</p>
          </div>
        </div>

        <label className="academic-field">
          Course ID
          <input
            value={courseId}
            onChange={(e) => setCourseId(e.target.value)}
            placeholder="e.g. agentic-ai"
          />
        </label>

        <div className="academic-assessments">
          {assessments.map((assessment, index) => (
            <div className="academic-assessment-row" key={index}>
              <label>
                Assessment name
                <input
                  value={assessment.name}
                  onChange={(e) => updateAssessment(index, 'name', e.target.value)}
                  placeholder={`e.g. Quiz ${index + 1}`}
                />
              </label>
              <label>
                Weight (%)
                <input
                  type="number"
                  min="0.01"
                  max="100"
                  value={assessment.weight}
                  onChange={(e) => updateAssessment(index, 'weight', e.target.value)}
                  placeholder="20"
                />
              </label>
              <label>
                Maximum marks
                <input
                  type="number"
                  min="0.01"
                  value={assessment.maximum}
                  onChange={(e) => updateAssessment(index, 'maximum', e.target.value)}
                  placeholder="10"
                />
              </label>
              <button
                type="button"
                className="academic-remove-button"
                onClick={() =>
                  setAssessments((previous) =>
                    previous.filter((_, i) => i !== index),
                  )
                }
                disabled={assessments.length <= 1}
                aria-label={`Remove assessment ${index + 1}`}
              >
                <X size={16} />
              </button>
            </div>
          ))}
        </div>

        <div className="academic-policy-actions">
          <button
            type="button"
            className="secondary-button"
            onClick={() =>
              setAssessments((previous) => [
                ...previous,
                { name: '', weight: '', maximum: '' },
              ])
            }
          >
            <Plus size={16} /> Add assessment
          </button>
        </div>

        <div className="academic-policy-options">
          <label>
            Pass percentage
            <input
              type="number"
              min="0"
              max="100"
              value={passPercentage}
              onChange={(e) => setPassPercentage(e.target.value)}
            />
          </label>

          <label>
            Missing marks
            <select
              value={missingPolicy}
              onChange={(e) =>
                setMissingPolicy(e.target.value as 'exclude' | 'zero')
              }
            >
              <option value="exclude">Exclude and normalize remaining weights</option>
              <option value="zero">Count missing marks as zero</option>
            </select>
          </label>
        </div>

        <button
          type="button"
          className="primary-button"
          onClick={savePolicy}
          disabled={policyLoading}
        >
          {policyLoading ? 'Saving policy…' : 'Save grading policy'}
        </button>

        {policyMessage && (
          <p className="academic-success" role="status">{policyMessage}</p>
        )}
      </section>

      <section className="academic-card">
        <h3>Upload class marks</h3>
        <p>Upload a marks file whose assessment column names match the saved policy.</p>

        <label className="academic-field">
          CSV or XLSX file
          <input
            type="file"
            accept=".csv,.xlsx"
            onChange={(e) => setMarksFile(e.target.files?.[0] ?? null)}
          />
        </label>

        {marksFile && (
          <p className="academic-file-name">
            <FileText size={16} /> {marksFile.name}
          </p>
        )}

        <button
          type="button"
          className="primary-button"
          onClick={uploadMarks}
          disabled={uploadLoading || !marksFile}
        >
          {uploadLoading ? 'Evaluating class…' : 'Evaluate class'}
        </button>

        <button
          type="button"
          className="secondary-button"
          onClick={analyzeClass}
          disabled={analyticsLoading || !marksFile}
        >
          {analyticsLoading ? 'Analyzing class…' : 'Analyze class trends'}
        </button>

        {analyticsError && (
          <div className="feedback error-feedback" role="alert">
            <AlertCircle size={19} />
            <div>
              <strong>Analytics unavailable</strong>
              <p>{analyticsError}</p>
            </div>
          </div>
        )}

      </section>

      {error && (
        <div className="feedback error-feedback" role="alert">
          <AlertCircle size={19} />
          <div><strong>Unable to continue</strong><p>{error}</p></div>
          <button
            className="feedback-close"
            onClick={() => setError('')}
            aria-label="Dismiss error"
          >
            <X size={16} />
          </button>
        </div>
      )}

      {evaluation && (
        <section className="academic-card">
          <div className="academic-section-heading">
            <div>
              <h3>Class evaluation</h3>
              <p>Course: {evaluation.course_id}</p>
            </div>
            <span className="academic-student-count">
              {evaluation.number_of_students} students
            </span>
          </div>

          <div className="academic-summary-grid">
            <article>
              <span>Class average</span>
              <strong>{classAverage === null ? '—' : `${classAverage.toFixed(1)}%`}</strong>
            </article>
            <article>
              <span>Passed</span>
              <strong>{passCount}</strong>
            </article>
            <article>
              <span>Failed</span>
              <strong>{failCount}</strong>
            </article>
            <article>
              <span>Provisional / not assessed</span>
              <strong>
                {evaluation.student_results.filter(
                  (s) => s.pass_status === 'provisional' || s.pass_status === 'not_assessed',
                ).length}
              </strong>
            </article>
          </div>

          <h4>Student results</h4>
          <div className="academic-table-wrap">
            <table className="academic-table">
              <thead>
                <tr>
                  <th>Student ID</th>
                  <th>Weighted score</th>
                  <th>Status</th>
                  <th>Complete</th>
                </tr>
              </thead>
              <tbody>
                {evaluation.student_results.map((student) => (
                  <tr
                    key={student.student_id}
                    className={student.student_id === selectedStudentId ? 'selected' : ''}
                    onClick={() => setSelectedStudentId(student.student_id)}
                  >
                    <td>
                      <button
                        type="button"
                        className="academic-student-link"
                        onClick={() => setSelectedStudentId(student.student_id)}
                      >
                        {student.student_id}
                      </button>
                    </td>
                    <td>
                      {student.weighted_percentage === null
                        ? '—'
                        : `${student.weighted_percentage.toFixed(2)}%`}
                    </td>
                    <td>
                      <span className={`academic-status ${student.pass_status}`}>
                        {student.pass_status.replace('_', ' ')}
                      </span>
                    </td>
                    <td>{student.is_complete ? 'Yes' : 'No'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {selectedStudent && (
            <div className="academic-student-detail">
              <h4>Student summary: {selectedStudent.student_id}</h4>
              <p>
                <strong>Weighted percentage:</strong>{' '}
                {selectedStudent.weighted_percentage === null
                  ? 'Not available'
                  : `${selectedStudent.weighted_percentage.toFixed(2)}%`}
              </p>
              <p><strong>Status:</strong> {selectedStudent.pass_status.replace('_', ' ')}</p>
              <p><strong>Complete:</strong> {selectedStudent.is_complete ? 'Yes' : 'No'}</p>
              <p><strong>Notes:</strong> {selectedStudent.message}</p>
              {selectedStudent.missing_assessments.length > 0 && (
                <p>
                  <strong>Missing assessments:</strong>{' '}
                  {selectedStudent.missing_assessments.join(', ')}
                </p>
              )}
            </div>
          )}
        </section>
      )}
      
      {analytics && (
        <section className="academic-card">
          <div className="academic-section-heading">
            <div>
              <h3>Class performance insights</h3>
              <p>
                Descriptive statistics based on the uploaded marks file.
                These are separate from official weighted grades.
              </p>
            </div>
          </div>

          <div className="academic-summary-grid">
            <article>
              <span>Students analyzed</span>
              <strong>{analytics.number_of_students}</strong>
            </article>
            <article>
              <span>Descriptive class average</span>
              <strong>
                {descriptiveClassAverage === null
                  ? '—'
                  : `${descriptiveClassAverage.toFixed(1)}%`}
              </strong>
            </article>
            <article>
              <span>Lower relative-performance group</span>
              <strong>{lowerPerformanceCount}</strong>
            </article>
            <article>
              <span>Students with missing marks</span>
              <strong>{studentsWithMissingMarks}</strong>
            </article>
          </div>

          <h4>Assessment-wise performance</h4>

          <div className="academic-assessment-analytics">
            {Object.entries(analytics.class_assessments).map(([name, stats]) => (
              <article className="academic-assessment-stat" key={name}>
                <div className="academic-assessment-stat-heading">
                  <strong>{name}</strong>
                  <span>
                    {stats.mean_percentage == null
                      ? 'Percentage unavailable'
                      : `${stats.mean_percentage.toFixed(1)}% average`}
                  </span>
                </div>

                {stats.mean_percentage != null && (
                  <div className="academic-progress-track">
                    <div
                      className="academic-progress-fill"
                      style={{
                        width: `${Math.min(100, Math.max(0, stats.mean_percentage))}%`,
                      }}
                    />
                  </div>
                )}

                <p>
                  Median:{' '}
                  {stats.median_percentage == null
                    ? '—'
                    : `${stats.median_percentage.toFixed(1)}%`}
                  {' · '}
                  Missing marks: {stats.missing_marks}
                  {' · '}
                  Students assessed: {stats.students_with_marks}
                </p>
              </article>
            ))}
          </div>

          <h4>Explore individual students</h4>

          <label className="academic-field">
            Select student
            <select
              value={selectedAnalyticsStudent}
              onChange={(event) => setSelectedAnalyticsStudent(event.target.value)}
            >
              {analytics.student_summaries.map((student) => (
                <option key={student.student_id} value={student.student_id}>
                  {student.student_id}
                </option>
              ))}
            </select>
          </label>

          {selectedAnalyticsRecord && (
            <div className="academic-student-detail">
              <h4>{selectedAnalyticsRecord.student_id}</h4>

              <p>
                <strong>Descriptive average:</strong>{' '}
                {selectedAnalyticsRecord.descriptive_average_percentage == null
                  ? 'Insufficient percentage data'
                  : `${selectedAnalyticsRecord.descriptive_average_percentage.toFixed(2)}%`}
              </p>

              <p>
                <strong>Relative performance:</strong>{' '}
                {selectedAnalyticsRecord.relative_performance.replaceAll('_', ' ')}
              </p>

              <div className="academic-table-wrap">
                <table className="academic-table">
                  <thead>
                    <tr>
                      <th>Assessment</th>
                      <th>Marks</th>
                      <th>Percentage</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(selectedAnalyticsRecord.assessments).map(
                      ([name, assessment]) => (
                        <tr key={name}>
                          <td>{name}</td>
                          <td>
                            {assessment.marks == null
                              ? 'Missing'
                              : `${assessment.marks}${assessment.maximum_marks == null ? '' : ` / ${assessment.maximum_marks}`}`}
                          </td>
                          <td>
                            {assessment.percentage == null
                              ? '—'
                              : `${assessment.percentage.toFixed(1)}%`}
                          </td>
                        </tr>
                      ),
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          <p className="academic-analytics-note">
            The lower relative-performance group is identified using the configured
            percentile cutoff. This is an academic support indicator, not proof of
            a conceptual learning difficulty.
          </p>
        </section>
      )}

    </div>
  )
}
