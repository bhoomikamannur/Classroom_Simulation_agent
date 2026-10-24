
import { useRef, useState, useEffect} from 'react'
import {
  BrainCircuit,
  GraduationCap,
  ArrowRight,
  Files,
  ChartNoAxesCombined,
  MessageCircle,
  ShieldCheck,
  Sparkles,
  Users,
  LibraryBig,
  LayoutDashboard,
  Upload,
  FileText,
  CheckCircle2,
  AlertCircle,
  LoaderCircle,
  ArrowLeft,
  BookOpen,
  X,
} from 'lucide-react'
import {
  Bot,
  Plus,
  UserRound,
  BookOpenCheck,
  Send,
} from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import './App.css'

type Role = 'teacher' | 'student' | null

type UploadResult = {
  filename: string
  source_type: string
  pages_or_slides_extracted: number
  chunks_stored: number
}

type TutorSource = Record<string, unknown>

type ChatMessage = {
  id: string
  role: 'user' | 'assistant'
  content: string
  sources?: TutorSource[]
}

type TutorResponse = {
  answer: string
  sources?: TutorSource[]
}


const CHAT_STORAGE_KEY = 'classroom-ai-tutor-chats-v2'


type SavedTutorChat = {
  id: string
  title: string
  sessionId: string
  messages: ChatMessage[]
  updatedAt: number
}



const WELCOME_MESSAGE: ChatMessage = {
  id: 'welcome',
  role: 'assistant',
  content:
    "Hi! I'm your AI Tutor. Ask me anything about your course materials, and I'll help you understand the concepts step by step.",
}

function createNewChat(): SavedTutorChat {
  return {
    id: `chat-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    title: 'New conversation',
    sessionId: `demo-session-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    messages: [{ ...WELCOME_MESSAGE }],
    updatedAt: Date.now(),
  }
}

function loadSavedChats(): SavedTutorChat[] {
  try {
    const saved = localStorage.getItem(CHAT_STORAGE_KEY)

    if (saved) {
      const parsed: unknown = JSON.parse(saved)

      if (
        Array.isArray(parsed) &&
        parsed.every(
          (chat: unknown) =>
            typeof chat === 'object' &&
            chat !== null &&
            'id' in chat &&
            typeof chat.id === 'string' &&
            'title' in chat &&
            typeof chat.title === 'string' &&
            'sessionId' in chat &&
            typeof chat.sessionId === 'string' &&
            'messages' in chat &&
            Array.isArray(chat.messages) &&
            'updatedAt' in chat &&
            typeof chat.updatedAt === 'number',
        )
      ) {
        return parsed as SavedTutorChat[]
      }
    }
  } catch {
    console.error('Unable to load saved tutor chats.')
  }

  return [createNewChat()]
}


type AcademicAssessment = {
  name: string
  weight: string
  maximum: string
}

type EvaluatedStudent = {
  student_id: string
  course_id: string
  weighted_percentage: number | null
  pass_status: 'pass' | 'fail' | 'provisional' | 'not_assessed'
  is_complete: boolean
  missing_assessments: string[]
  message: string
}

type AcademicEvaluationResponse = {
  course_id: string
  number_of_students: number
  grading_policy: {
    assessment_weights: Record<string, number>
    assessment_max_marks: Record<string, number>
    pass_percentage: number
    missing_marks_policy: 'exclude' | 'zero'
  }
  student_results: EvaluatedStudent[]
}


type ClassAnalyticsResponse = {
  student_id_column: string
  number_of_students: number
  number_of_assessments: number
  assessment_max_marks: Record<string, number>
  class_assessments: Record<
    string,
    {
      students_with_marks: number
      missing_marks: number
      mean_raw_marks: number | null
      median_raw_marks: number | null
      mean_percentage?: number | null
      median_percentage?: number | null
      standard_deviation_percentage?: number | null
    }
  >
  student_summaries: {
    student_id: string
    assessments: Record<
      string,
      {
        marks: number | null
        maximum_marks: number | null
        percentage: number | null
      }
    >
    descriptive_average_percentage: number | null
    relative_performance: string
  }[]
  relative_performance_threshold: {
    percentile: number
    cutoff_average_percentage: number | null
  }
  interpretation_notes: string[]
}


type PerformanceResult = {
  student_id: string
  subject_id: string
  diagnosis: {
    concepts?: {
      concept: string
      understanding: string
      evidence?: string[]
      misconceptions?: string[]
    }[]
    strengths?: string[]
    weaknesses?: string[]
    overall_observation?: string
    confidence?: string
  }
}

type InterventionResult = {
  student_id: string
  subject_id: string
  intervention?: {
    priority?: string
    objective?: string
    explanation?: string
    activity?: string
    follow_up_question?: string
    success_criteria?: string
  }
  teacher_insight?: {
    observed_learning_state?: string
    evidence_summary?: string
    recommended_teaching_action?: string
    next_step?: string
  }
}

type PerformanceApiResponse = {
  performance: PerformanceResult
  intervention: InterventionResult
}

function PerformancePanel() {
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
      const response = await fetch('/api/performance/intervene', {
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
  const intervention = result?.intervention.intervention
  const insight = result?.intervention.teacher_insight

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


function AcademicEvaluationPanel() {
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
      const existing = await fetch(url)

      let response: Response

      if (existing.ok) {
        response = await fetch(url, {
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
        response = await fetch('/api/academic-policies', {
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
      const response = await fetch('/api/academic-evaluation/upload', {
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
      const response = await fetch('/api/academic-evaluation/analyze', {
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


function App() {
  const [role, setRole] = useState<Role>(null)
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState('')
  const [uploadResult, setUploadResult] = useState<UploadResult | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  
  const [savedChats, setSavedChats] =
    useState<SavedTutorChat[]>(loadSavedChats)

  const [activeChatId, setActiveChatId] =
    useState(() => loadSavedChats()[0]?.id ?? '')

  const activeChat =
    savedChats.find((chat) => chat.id === activeChatId) ??
    savedChats[0]

  const chatMessages = activeChat?.messages ?? []
  const sessionId = activeChat?.sessionId ?? ''

  const [chatInput, setChatInput] = useState('')
  const [chatLoading, setChatLoading] = useState(false)
  const [chatError, setChatError] = useState('')
  
  
  useEffect(() => {
    try {
      localStorage.setItem(
        CHAT_STORAGE_KEY,
        JSON.stringify(savedChats),
      )
    } catch (error) {
      console.error('Unable to save tutor chat history:', error)
    }
  }, [savedChats])

  function updateActiveChat(
    updater: (chat: SavedTutorChat) => SavedTutorChat,
  ) {
    setSavedChats((previous) =>
      previous.map((chat) =>
        chat.id === activeChatId
          ? updater(chat)
          : chat,
      ),
    )
  }

  function startNewChat() {
    const newChat = createNewChat()

    setSavedChats((previous) => [newChat, ...previous])
    setActiveChatId(newChat.id)
    setChatInput('')
    setChatError('')
  }

  function openChat(chatId: string) {
    setActiveChatId(chatId)
    setChatInput('')
    setChatError('')
  }

  async function sendTutorMessage() {
    const message = chatInput.trim()

    if (!message || chatLoading) return

    setChatInput('')
    setChatError('')
    setChatLoading(true)

    const userMessage: ChatMessage = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: message,
    }

    updateActiveChat((chat) => ({
      ...chat,
      title:
        chat.title === 'New conversation'
          ? message.slice(0, 45) + (message.length > 45 ? '…' : '')
          : chat.title,
      messages: [...chat.messages, userMessage],
      updatedAt: Date.now(),
    }))

    try {
      const response = await fetch('/api/tutor/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          student_id: 'demo-student-001',
          subject_id: 'agentic-ai',
          session_id: sessionId,
          message,
          top_k: 5,
        }),
      })

      const data = await response.json()

      if (!response.ok) {
        throw new Error(
          typeof data.detail === 'string'
            ? data.detail
            : 'The tutor could not answer your question.',
        )
      }

      const result = data as TutorResponse

      if (typeof result.answer !== 'string') {
        throw new Error('The tutor returned an unexpected response.')
      }

      updateActiveChat((chat) => ({
        ...chat,
        messages: [
          ...chat.messages,
          {
            id: `assistant-${Date.now()}`,
            role: 'assistant',
            content: result.answer,
            sources: result.sources ?? [],
          },
        ],
        updatedAt: Date.now(),
      }))
    } catch (error) {
      setChatError(
        error instanceof Error
          ? error.message
          : 'Unable to connect to the Tutor Agent.',
      )
      setChatInput(message)
    } finally {
      setChatLoading(false)
    }
  }

  

  function openRole(nextRole: Exclude<Role, null>) {
    setRole(nextRole)
    setSelectedFile(null)
    setUploadError('')
    setUploadResult(null)
  }

  function chooseFile(file: File | undefined) {
    setUploadError('')
    setUploadResult(null)

    if (!file) {
      setSelectedFile(null)
      return
    }

    const valid = /\.(pdf|pptx)$/i.test(file.name)

    if (!valid) {
      setSelectedFile(null)
      setUploadError('Please choose a PDF or PPTX file.')
      if (fileInputRef.current) fileInputRef.current.value = ''
      return
    }

    setSelectedFile(file)
  }

  async function uploadDocument() {
    if (!selectedFile || uploading) return

    setUploading(true)
    setUploadError('')
    setUploadResult(null)

    const formData = new FormData()
    formData.append('file', selectedFile)

    try {
      const response = await fetch('/api/documents/upload', {
        method: 'POST',
        body: formData,
      })

      const data = await response.json()

      if (!response.ok) {
        const detail =
          typeof data.detail === 'string'
            ? data.detail
            : 'The document could not be processed.'
        throw new Error(detail)
      }

      setUploadResult(data as UploadResult)
      setSelectedFile(null)

      if (fileInputRef.current) fileInputRef.current.value = ''
    } catch (error) {
      setUploadError(
        error instanceof Error
          ? error.message
          : 'Could not connect to the backend. Check that FastAPI is running.',
      )
    } finally {
      setUploading(false)
    }
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <a className="brand" href="#home" onClick={() => setRole(null)}>
          <span className="brand-icon">
            <BrainCircuit size={25} />
          </span>
          <span>
            <strong>Classroom AI</strong>
            <small>Intelligent Learning Platform</small>
          </span>
        </a>

        <div className="topbar-right">
          <span className="status-dot" />
          <span className="status-text">Learning, reimagined</span>
        </div>
      </header>

      {!role && (
        <section className="welcome-section" id="home">
          <div className="eyebrow">
            <Sparkles size={15} />
            YOUR AI-POWERED CLASSROOM
          </div>

          <h1>
            A smarter way to
            <br />
            <span>teach and learn.</span>
          </h1>

          <p className="welcome-copy">
            One intelligent classroom. Two connected experiences.
            Empower educators with insights and help students learn
            with a personal AI tutor.
          </p>

          <div className="role-grid">
            <button
              className="role-card teacher-card"
              onClick={() => openRole('teacher')}
            >
              <div className="role-card-top">
                <span className="role-icon teacher-icon">
                  <LibraryBig size={26} />
                </span>
                <span className="role-arrow"><ArrowRight size={20} /></span>
              </div>
              <span className="role-label">FOR EDUCATORS</span>
              <h2>Teacher workspace</h2>
              <p>
                Manage course materials, review student performance,
                and discover actionable learning insights.
              </p>
              <div className="feature-list">
                <span><Files size={16} /> Course materials</span>
                <span><ChartNoAxesCombined size={16} /> Performance insights</span>
                <span><ShieldCheck size={16} /> Academic policies</span>
              </div>
              <span className="card-action">
                Enter teacher workspace <ArrowRight size={16} />
              </span>
            </button>

            <button
              className="role-card student-card"
              onClick={() => openRole('student')}
            >
              <div className="role-card-top">
                <span className="role-icon student-icon">
                  <GraduationCap size={27} />
                </span>
                <span className="role-arrow"><ArrowRight size={20} /></span>
              </div>
              <span className="role-label">FOR LEARNERS</span>
              <h2>Student workspace</h2>
              <p>
                Explore concepts, ask questions, and get personalized
                explanations from your AI learning companion.
              </p>
              <div className="feature-list">
                <span><MessageCircle size={16} /> AI tutor conversations</span>
                <span><BookOpen size={16} /> Course-based learning</span>
                <span><BrainCircuit size={16} /> Guided explanations</span>
              </div>
              <span className="card-action">
                Start learning <ArrowRight size={16} />
              </span>
            </button>
          </div>

          <div className="trust-row">
            <span><ShieldCheck size={16} /> Built for education</span>
            <span><BrainCircuit size={16} /> Multi-agent AI architecture</span>
            <span><Users size={16} /> Teacher and student experiences</span>
          </div>
        </section>
      )}

      {role === 'teacher' && (
        <section className="dashboard">
          <aside className="dashboard-sidebar">
            <div className="sidebar-heading">TEACHER PORTAL</div>
            <button className="sidebar-link active">
              <LayoutDashboard size={18} /> Overview
            </button>
            <button
              className="sidebar-link"
              onClick={() => document.getElementById('materials')?.scrollIntoView({ behavior: 'smooth' })}
            >
              <Files size={18} /> Course materials
            </button>
            <button
              className="sidebar-link"
              onClick={() => document.getElementById('performance')?.scrollIntoView({ behavior: 'smooth' })}
            >
              <ChartNoAxesCombined size={18} /> Performance
            </button>
            <div className="sidebar-bottom">
              <span className="sidebar-avatar">T</span>
              <span><strong>Teacher</strong><small>Educator workspace</small></span>
            </div>
          </aside>

          <div className="dashboard-main">
            <button className="back-button dashboard-back" onClick={() => setRole(null)}>
              <ArrowLeft size={15} /> All workspaces
            </button>

            <div className="dashboard-heading">
              <div>
                <span className="eyebrow">TEACHER WORKSPACE</span>
                <h1>Good to see you.</h1>
                <p>Manage learning resources and explore student progress.</p>
              </div>
              <div className="dashboard-heading-icon">
                <LibraryBig size={25} />
              </div>
            </div>

            <div className="stats-grid">
              <article className="stat-card">
                <span className="stat-icon purple"><Files size={20} /></span>
                <span className="stat-label">Upload capability</span>
                <strong>PDF & PPTX</strong>
                <small>Course materials supported</small>
              </article>
              <article className="stat-card">
                <span className="stat-icon teal"><BrainCircuit size={20} /></span>
                <span className="stat-label">Knowledge pipeline</span>
                <strong>RAG enabled</strong>
                <small>Chunks stored on successful upload</small>
              </article>
              <article className="stat-card">
                <span className="stat-icon orange"><ChartNoAxesCombined size={20} /></span>
                <span className="stat-label">Academic insights</span>
                <strong>Ready to explore</strong>
                <small>Marks evaluation and interventions</small>
              </article>
            </div>

            <section className="panel upload-panel" id="materials">
              <div className="panel-heading">
                <div>
                  <span className="panel-kicker">KNOWLEDGE BASE</span>
                  <h2>Course materials</h2>
                  <p>Upload lecture slides or reading materials to the course knowledge base.</p>
                </div>
                <span className="panel-heading-icon"><Files size={22} /></span>
              </div>

              <div className="upload-dropzone">
                <span className="upload-icon"><Upload size={25} /></span>
                <h3>{selectedFile ? selectedFile.name : 'Upload course material'}</h3>
                <p>
                  {selectedFile
                    ? `${(selectedFile.size / (1024 * 1024)).toFixed(2)} MB · Ready to upload`
                    : 'Choose a PDF document or PowerPoint presentation (.pptx).'}
                </p>

                <input
                  ref={fileInputRef}
                  className="file-input"
                  type="file"
                  accept=".pdf,.pptx,application/pdf,application/vnd.openxmlformats-officedocument.presentationml.presentation"
                  onChange={(event) => chooseFile(event.target.files?.[0])}
                />

                <div className="upload-actions">
                  <button
                    className="secondary-button"
                    onClick={() => fileInputRef.current?.click()}
                    disabled={uploading}
                  >
                    <FileText size={16} /> Choose file
                  </button>
                  <button
                    className="primary-button"
                    onClick={uploadDocument}
                    disabled={!selectedFile || uploading}
                  >
                    {uploading
                      ? <><LoaderCircle className="spin" size={16} /> Processing...</>
                      : <><Upload size={16} /> Upload material</>}
                  </button>
                </div>
                <small className="format-note">
                  <ShieldCheck size={13} /> PDF and PPTX · Uploads are processed by your FastAPI backend
                </small>
              </div>

              {uploadError && (
                <div className="feedback error-feedback" role="alert">
                  <AlertCircle size={19} />
                  <div><strong>Upload failed</strong><p>{uploadError}</p></div>
                  <button className="feedback-close" onClick={() => setUploadError('')} aria-label="Dismiss error">
                    <X size={16} />
                  </button>
                </div>
              )}

              {uploadResult && (
                <div className="feedback success-feedback" role="status">
                  <CheckCircle2 size={21} />
                  <div className="result-content">
                    <strong>Material processed successfully</strong>
                    <p>{uploadResult.filename}</p>
                    <div className="result-stats">
                      <span>{uploadResult.pages_or_slides_extracted} pages/slides extracted</span>
                      <span>{uploadResult.chunks_stored} chunks stored</span>
                    </div>
                  </div>
                  <button className="feedback-close" onClick={() => setUploadResult(null)} aria-label="Dismiss result">
                    <X size={16} />
                  </button>
                </div>
              )}
            </section>

            <section className="panel performance-panel" id="performance">
              <div className="panel-heading">
                <div>
                  <span className="panel-kicker">STUDENT SUCCESS</span>
                  <h2>Performance & evaluation</h2>
                  <p>Use academic policies and marks data to support evidence-based teaching.</p>
                </div>
                <span className="panel-heading-icon teal-bg"><ChartNoAxesCombined size={22} /></span>
              </div>
              <AcademicEvaluationPanel />
              <PerformancePanel />
            </section>
          </div>
        </section>
      )}

      
      {role === 'student' && (
        <section className="student-dashboard">
          <aside className="student-sidebar">
            <button
              className="student-brand"
              onClick={() => setRole(null)}
            >
              <span className="brand-icon">
                <BrainCircuit size={23} />
              </span>
              <span>
                <strong>Classroom AI</strong>
                <small>Student workspace</small>
              </span>
            </button>

            <div className="student-sidebar-label">LEARNING SPACE</div>

            <button className="student-nav active">
              <MessageCircle size={17} />
              AI Tutor
            </button>

            <div className="chat-history-section">
              <div className="chat-history-heading">
                <span>YOUR CHATS</span>
                <button
                  type="button"
                  onClick={startNewChat}
                  aria-label="Start a new chat"
                  title="Start a new chat"
                >
                  <Plus size={16} />
                </button>
              </div>

              <div className="chat-history-list">
                {savedChats.map((chat) => (
                  <button
                    type="button"
                    key={chat.id}
                    className={`chat-history-item ${
                      chat.id === activeChatId ? 'active' : ''
                    }`}
                    onClick={() => openChat(chat.id)}
                    title={chat.title}
                  >
                    <MessageCircle size={15} />
                    <span>{chat.title}</span>
                  </button>
                ))}
              </div>
            </div>


            <div className="student-course-card">
              <BookOpenCheck size={19} />
              <strong>Course learning</strong>
              <p>Ask questions about your uploaded learning materials.</p>
            </div>

            <div className="student-profile">
              <span className="student-avatar">S</span>
              <span>
                <strong>Demo Student</strong>
                <small>Learning workspace</small>
              </span>
            </div>
          </aside>

          <div className="chat-workspace">
            <header className="chat-header">
              <button
                className="chat-back"
                onClick={() => setRole(null)}
              >
                <ArrowLeft size={16} />
              </button>

              <span className="chat-agent-icon">
                <Bot size={23} />
              </span>

              <div className="chat-header-copy">
                <strong>AI Learning Tutor</strong>
                <span>
                  <span className="status-dot" />
                  Course-aware learning assistant
                </span>
              </div>

              <button
                className="new-chat-button"
                disabled={chatLoading}
                onClick={startNewChat}
              >
                <Plus size={16} />
                <span>New chat</span>
              </button>
            </header>

            <div className="chat-context-banner">
              <BookOpenCheck size={17} />
              <span>
                <strong>Learning from course materials</strong>
                <small>
                  Answers use retrieved course content when relevant.
                </small>
              </span>
            </div>

            <div className="chat-messages" aria-live="polite">
              {chatMessages.map((message) => (
                <article
                  className={`chat-message ${message.role}`}
                  key={message.id}
                >
                  <span className={`message-avatar ${message.role}`}>
                    {message.role === 'assistant'
                      ? <Bot size={18} />
                      : <UserRound size={18} />}
                  </span>

                  <div className="message-body">
                    <span className="message-author">
                      {message.role === 'assistant'
                        ? 'AI Tutor'
                        : 'You'}
                    </span>

                    <div className="message-bubble">
                      {message.role === 'assistant' ? (
                        <ReactMarkdown>{message.content}</ReactMarkdown>
                      ) : (
                        message.content
                      )}
                    </div>

                    {message.role === 'assistant' &&
                      message.sources &&
                      message.sources.length > 0 && (
                        <div className="source-list">
                          <span className="source-heading">
                            <BookOpenCheck size={14} />
                            Retrieved course sources
                          </span>

                          {message.sources.map((source, index) => {
                            const rawName =
                              typeof source.source_name === 'string'
                                ? source.source_name
                                : 'Course material'

                            const name = rawName.split(/[\\/]/).pop() || 'Course material'

                            const location =
                              source.page != null
                                ? `Page ${String(source.page)}`
                                : source.slide != null
                                  ? `Slide ${String(source.slide)}`
                                  : ''

                            return (
                              <div
                                className="source-chip"
                                key={`${name}-${location}-${index}`}
                              >
                                <FileText size={14} />
                                <span>{name}</span>
                                {location && <small>{location}</small>}
                              </div>
                            )
                          })}
                        </div>
                      )}
                  </div>
                </article>
              ))}

              {chatLoading && (
                <div className="typing-indicator" role="status">
                  <span className="message-avatar assistant">
                    <Bot size={18} />
                  </span>
                  <div>
                    <span className="message-author">AI Tutor</span>
                    <div className="typing-bubble">
                      <LoaderCircle className="spin" size={17} />
                      Thinking through your question...
                    </div>
                  </div>
                </div>
              )}
            </div>

            {chatError && (
              <div className="chat-error" role="alert">
                <AlertCircle size={16} />
                <span>{chatError}</span>
              </div>
            )}

            <form
              className="chat-composer"
              onSubmit={(event) => {
                event.preventDefault()
                void sendTutorMessage()
              }}
            >
              <textarea
                value={chatInput}
                onChange={(event) => setChatInput(event.target.value)}
                onKeyDown={(event) => {
                  if (
                    event.key === 'Enter' &&
                    !event.shiftKey &&
                    !event.nativeEvent.isComposing
                  ) {
                    event.preventDefault()
                    void sendTutorMessage()
                  }
                }}
                placeholder="Ask a question about your course..."
                aria-label="Message the AI Tutor"
                rows={2}
                disabled={chatLoading}
              />

              <div className="composer-footer">
                <span>Enter to send · Shift + Enter for a new line</span>

                <button
                  type="submit"
                  className="send-button"
                  disabled={!chatInput.trim() || chatLoading}
                  aria-label="Send message"
                >
                  {chatLoading
                    ? <LoaderCircle className="spin" size={18} />
                    : <Send size={18} />}
                </button>
              </div>
            </form>

            <p className="chat-disclaimer">
              AI-generated explanations may need verification against your course material.
            </p>
          </div>
        </section>
      )}


      <footer className="app-footer">
        <span>Classroom AI · Agentic Learning System</span>
        <span>Designed for better learning outcomes</span>
      </footer>
    </main>
  )
}

export default App
