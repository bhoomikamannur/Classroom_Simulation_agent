import { useEffect, useState } from 'react'
import { AlertCircle, RefreshCw, Upload, Trash2, ChevronDown, ChevronUp, Pencil, BarChart3, Users, CheckCircle2, AlertTriangle, TrendingUp } from 'lucide-react'
import { apiFetch } from '../../services/api'

type RegisterStudent = {
  student_id: string
  display_id?: string
  assessments: Record<string, number | null>
  assessment_maximums?: Record<string, number | null>
}
type Register = {
  course_id: string
  number_of_students: number
  assessment_names: Record<string, string>
  students: RegisterStudent[]
}
type EvaluationResult = {
  student_id: string
  display_id: string
  weighted_percentage: number | null
  pass_status: 'pass' | 'fail' | 'provisional' | 'not_assessed'
  is_complete: boolean
  missing_assessments: string[]
  message: string
}
type EvaluationSummary = {
  student_count: number
  evaluated_count: number
  complete_count: number
  provisional_count: number
  not_assessed_count: number
  pass_count: number
  fail_count: number
  class_average_percentage: number | null
  complete_average_percentage: number | null
  highest_percentage: number | null
  lowest_percentage: number | null
  pass_rate: number | null
  assessment_summary: Array<{
    assessment: string
    name: string
    weight: number
    maximum_marks: number
    students_with_marks: number
    average_percentage: number | null
  }>
}
type EvaluationReport = {
  grading_policy: { assessment_weights: Record<string, number>; assessment_max_marks: Record<string, number>; pass_percentage: number; missing_marks_policy: 'exclude' | 'zero' }
  student_results: EvaluationResult[]
  summary: EvaluationSummary
}
type UploadRecord = {
  upload_id: string
  filename: string
  uploaded_at: string
  student_count: number
  assessment_names: Record<string, string>
}

async function readJson<T>(response: Response): Promise<T> {
  const data = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Request failed.')
  return data as T
}

export function AcademicEvaluationPanel({ courseId }: { courseId: string }) {
  const [marksFile, setMarksFile] = useState<File | null>(null)
  const [register, setRegister] = useState<Register | null>(null)
  const [uploads, setUploads] = useState<UploadRecord[]>([])
  const [expanded, setExpanded] = useState(false)
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [assessmentConfig, setAssessmentConfig] = useState<Record<string, { weight: string; maximum: string }>>({})
  const [passPercentage, setPassPercentage] = useState('40')
  const [missingPolicy, setMissingPolicy] = useState<'exclude' | 'zero'>('exclude')
  const [evaluation, setEvaluation] = useState<EvaluationReport | null>(null)
  const visibleRows = expanded ? (register?.students ?? []) : (register?.students ?? []).slice(0, 10)

  async function refreshRegister() {
    const data = await readJson<Register>(await apiFetch(`/api/academic-evaluation/register/${encodeURIComponent(courseId)}`))
    setRegister(data)
    // Seed one editable configuration row for every detected assessment column.
    // Preserve values already entered by the professor when the register refreshes.
    setAssessmentConfig(current => {
      const next: Record<string, { weight: string; maximum: string }> = {}
      for (const key of Object.keys(data.assessment_names ?? {})) {
        next[key] = current[key] ?? { weight: '', maximum: '' }
      }
      return next
    })
  }

  async function refreshUploads() {
    const data = await readJson<{ uploads: UploadRecord[] }>(await apiFetch(`/api/academic-evaluation/uploads/${encodeURIComponent(courseId)}`))
    setUploads(data.uploads ?? [])
  }

  async function refreshSavedConfiguration() {
    try {
      const policy = await readJson<{ assessment_weights: Record<string, number>; assessment_max_marks: Record<string, number>; pass_percentage: number; missing_marks_policy: 'exclude' | 'zero' }>(
        await apiFetch(`/api/academic-policies/${encodeURIComponent(courseId)}`),
      )
      setAssessmentConfig(Object.fromEntries(Object.keys(policy.assessment_weights).map(key => [key, {
        weight: String(policy.assessment_weights[key]),
        maximum: String(policy.assessment_max_marks[key]),
      }])))
      setPassPercentage(String(policy.pass_percentage))
      setMissingPolicy(policy.missing_marks_policy)
    } catch {
      // A course without a saved evaluation configuration starts with blank fields.
    }
  }

  async function refreshAll() {
    setError('')
    try { await Promise.all([refreshRegister(), refreshUploads(), refreshSavedConfiguration()]) }
    catch (e) { setError(e instanceof Error ? e.message : 'Could not load academic marks.') }
  }

  useEffect(() => {
    setRegister(null); setUploads([]); setError(''); setMessage(''); setExpanded(false); setAssessmentConfig({}); setEvaluation(null)
    if (courseId) void refreshAll()
    // refreshAll is intentionally scoped to the selected course.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [courseId])

  async function uploadMarks() {
    if (!marksFile) return
    setBusy('upload'); setError(''); setMessage(''); setEvaluation(null)
    try {
      const body = new FormData()
      body.append('course_id', courseId)
      body.append('file', marksFile)
      const result = await readJson<{ students_updated: number; assessment_names: Record<string, string>; message: string }>(
        await apiFetch('/api/academic-evaluation/upload', { method: 'POST', body }),
      )
      setMessage(`${result.message} ${result.students_updated} students updated; added/updated ${Object.values(result.assessment_names).join(', ')}.`)
      setMarksFile(null)
      const fileInput = document.getElementById('academic-marks-file') as HTMLInputElement | null
      if (fileInput) fileInput.value = ''
      await Promise.all([refreshRegister(), refreshUploads()])
    } catch (e) { setError(e instanceof Error ? e.message : 'Marks upload failed.') }
    finally { setBusy('') }
  }

  async function deleteUpload(upload: UploadRecord) {
    if (!window.confirm(`Delete ${upload.filename}? Marks that still come from this file will be removed or restored from an earlier upload.`)) return
    setBusy(`delete:${upload.upload_id}`); setError(''); setMessage(''); setEvaluation(null)
    try {
      const result = await readJson<{ message: string }>(await apiFetch(
        `/api/academic-evaluation/uploads/${encodeURIComponent(courseId)}/${encodeURIComponent(upload.upload_id)}`,
        { method: 'DELETE' },
      ))
      setMessage(result.message)
      await Promise.all([refreshRegister(), refreshUploads()])
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not delete upload.') }
    finally { setBusy('') }
  }

  async function editMark(student: RegisterStudent, assessmentKey: string, current: number | null) {
    const name = register?.assessment_names[assessmentKey] ?? assessmentKey
    const entered = window.prompt(`Correct ${name} for ${student.display_id ?? student.student_id}. Leave blank to clear the mark.`, current == null ? '' : String(current))
    if (entered === null) return
    const value = entered.trim() === '' ? null : Number(entered)
    if (value !== null && (!Number.isFinite(value) || value < 0)) { setError('Enter a valid non-negative mark.'); return }
    setBusy('edit'); setError(''); setMessage(''); setEvaluation(null)
    try {
      await readJson(await apiFetch(`/api/academic-evaluation/marks/${encodeURIComponent(courseId)}`, {
        method: 'PATCH', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ student_identifier: student.display_id ?? student.student_id, assessment: assessmentKey, marks: value }),
      }))
      setMessage('Mark updated successfully.')
      await refreshRegister()
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not update mark.') }
    finally { setBusy('') }
  }

  async function evaluateMarks() {
    const entries = Object.entries(assessmentConfig)
    if (!entries.length) { setError('Keep at least one assessment to evaluate.'); return }
    const weights: Record<string, number> = {}
    const maximums: Record<string, number> = {}
    for (const [key, config] of entries) {
      const weight = Number(config.weight)
      const maximum = Number(config.maximum)
      if (!config.weight.trim() || !Number.isFinite(weight) || weight <= 0 || weight > 100) {
        setError(`Enter a valid weight between 0 and 100 for ${register?.assessment_names[key] ?? key}.`); return
      }
      if (!config.maximum.trim() || !Number.isFinite(maximum) || maximum <= 0) {
        setError(`Enter a positive maximum mark for ${register?.assessment_names[key] ?? key}.`); return
      }
      weights[key] = weight
      maximums[key] = maximum
    }
    const total = Object.values(weights).reduce((sum, value) => sum + value, 0)
    if (Math.abs(total - 100) > 0.000001) { setError(`Assessment weights must total 100%. Current total: ${total}%.`); return }
    const pass = Number(passPercentage)
    if (!Number.isFinite(pass) || pass < 0 || pass > 100) { setError('Pass percentage must be between 0 and 100.'); return }
    setBusy('evaluate'); setError(''); setMessage('')
    try {
      const report = await readJson<EvaluationReport & { message: string }>(await apiFetch(
        `/api/academic-evaluation/evaluate/${encodeURIComponent(courseId)}`,
        { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({
          assessment_weights: weights, assessment_max_marks: maximums,
          pass_percentage: pass, missing_marks_policy: missingPolicy,
        }) },
      ))
      setEvaluation(report)
      setMessage(report.message)
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not evaluate marks.') }
    finally { setBusy('') }
  }

  function removeAssessment(key: string) {
    setAssessmentConfig(current => {
      const next = { ...current }
      delete next[key]
      return next
    })
    setEvaluation(null)
  }

  const assessmentEntries = Object.entries(register?.assessment_names ?? {})

  return <div className="academic-evaluation">
    <section className="academic-card">
      <div className="academic-section-heading"><div><h3>Marks upload</h3><p>Upload assessment marks whenever they are available. New assessments become new columns; later uploads update only the assessments included in that file.</p></div></div>
      <label className="academic-field" htmlFor="academic-marks-file">Marks file (CSV/XLSX)
        <input id="academic-marks-file" type="file" accept=".csv,.xlsx" onChange={event => setMarksFile(event.target.files?.[0] ?? null)} />
      </label>
      <div className="academic-action-row">
        <button type="button" className="primary-button" disabled={!marksFile || busy === 'upload'} onClick={() => void uploadMarks()}>
          <Upload size={16}/>{busy === 'upload' ? 'Uploading…' : 'Upload / update marks'}
        </button>
        <button type="button" className="secondary-button" disabled={!!busy} onClick={() => void refreshAll()}><RefreshCw size={16}/> Refresh</button>
      </div>
      <div className="academic-upload-list">
        <h4>Uploaded marks files</h4>
        {uploads.length === 0 ? <p>No marks files uploaded yet.</p> : uploads.map(upload => (
          <div className="academic-upload-item" key={upload.upload_id}>
            <div><strong>{upload.filename}</strong><p>{Object.values(upload.assessment_names ?? {}).join(', ')} · {upload.student_count} students · {new Date(upload.uploaded_at).toLocaleString()}</p></div>
            <button type="button" className="secondary-button" disabled={busy === `delete:${upload.upload_id}`} onClick={() => void deleteUpload(upload)}><Trash2 size={15}/>{busy === `delete:${upload.upload_id}` ? 'Deleting…' : 'Delete'}</button>
          </div>
        ))}
      </div>
    </section>

    {error && <div className="feedback error-feedback" role="alert"><AlertCircle size={18}/><p>{error}</p></div>}
    {message && <p className="academic-success" role="status">{message}</p>}

    <section className="academic-card">
      <div className="academic-section-heading"><div><h3>Course marks register</h3><p>{register ? `${register.number_of_students} enrolled students · select a mark to edit it` : 'Loading enrolled students and marks…'}</p></div></div>
      {register && <>
        <div className="academic-table-wrap"><table className="academic-table"><thead><tr><th>Student roll number</th>{assessmentEntries.map(([key, name]) => <th key={key}>{name}</th>)}{evaluation && <><th>Weighted %</th><th>Result</th></>}</tr></thead>
          <tbody>{visibleRows.map(student => <tr key={student.student_id}><td>{student.display_id || student.student_id}</td>{assessmentEntries.map(([key]) => {
            const value = student.assessments?.[key] ?? null
            const maximum = student.assessment_maximums?.[key]
            return <td key={key}><button type="button" className="academic-mark-cell" title="Edit mark" disabled={busy === 'edit'} onClick={() => void editMark(student, key, value)}>{value == null ? '—' : value}{maximum != null ? <small className="academic-mark-maximum"> / {maximum}</small> : null}<Pencil size={11}/></button></td>
          })}{evaluation && (() => { const result = evaluation.student_results.find(item => item.student_id === student.student_id); return <><td>{result?.weighted_percentage == null ? '—' : `${result.weighted_percentage.toFixed(2)}%`}</td><td><span className={`academic-status ${result?.pass_status ?? ''}`}>{result?.pass_status?.replace('_', ' ') ?? '—'}</span>{result && !result.is_complete ? <small className="academic-result-note">Provisional</small> : null}</td></> })()}</tr>)}</tbody>
        </table></div>
        {register.students.length > 10 && <button type="button" className="secondary-button academic-expand-button" onClick={() => setExpanded(value => !value)}>{expanded ? <><ChevronUp size={16}/> View less</> : <><ChevronDown size={16}/> View all {register.students.length} students</>}</button>}
        {assessmentEntries.length === 0 && <p>No assessment marks have been uploaded yet.</p>}
      </>}
    </section>

    <section className="academic-card">
      <div className="academic-section-heading"><div><h3>Assessment configuration</h3><p>Assessment names are detected from uploaded marks files. Remove non-assessment columns, then enter each assessment's weight and maximum marks.</p></div></div>
      {assessmentEntries.length === 0 ? <p>Upload a marks file to detect assessment columns.</p> : <>
        <div className="academic-config-table-wrap"><table className="academic-table academic-config-table"><thead><tr><th>Assessment</th><th>Weight (%)</th><th>Maximum marks</th><th>Action</th></tr></thead><tbody>
          {assessmentEntries.filter(([key]) => key in assessmentConfig).map(([key, name]) => <tr key={key}>
            <td><strong>{name}</strong></td>
            <td><input aria-label={`${name} weight percentage`} type="number" min="0.01" max="100" step="0.01" placeholder="Enter weight" value={assessmentConfig[key]?.weight ?? ''} onChange={event => { setEvaluation(null); setAssessmentConfig(current => ({ ...current, [key]: { ...current[key], weight: event.target.value } })) }}/></td>
            <td><input aria-label={`${name} maximum marks`} type="number" min="0.01" step="0.01" placeholder="Enter maximum" value={assessmentConfig[key]?.maximum ?? ''} onChange={event => { setEvaluation(null); setAssessmentConfig(current => ({ ...current, [key]: { ...current[key], maximum: event.target.value } })) }}/></td>
            <td><button type="button" className="academic-remove-button" title={`Remove ${name} from evaluation`} aria-label={`Remove ${name}`} onClick={() => removeAssessment(key)}><Trash2 size={16}/></button></td>
          </tr>)}
        </tbody></table></div>
        <div className="academic-evaluation-options">
          <label>Pass percentage<input type="number" min="0" max="100" value={passPercentage} onChange={event => { setEvaluation(null); setPassPercentage(event.target.value) }}/></label>
          <label>Missing marks<select value={missingPolicy} onChange={event => { setEvaluation(null); setMissingPolicy(event.target.value as 'exclude' | 'zero') }}><option value="exclude">Exclude and calculate provisional result</option><option value="zero">Count missing marks as zero</option></select></label>
          <div className="academic-weight-total">Total weight: <strong>{Object.values(assessmentConfig).reduce((sum, item) => sum + (Number(item.weight) || 0), 0).toFixed(2)}%</strong></div>
        </div>
        <div className="academic-action-row academic-evaluate-action"><button type="button" className="primary-button" disabled={!!busy || !assessmentEntries.some(([key]) => key in assessmentConfig)} onClick={() => void evaluateMarks()}>{busy === 'evaluate' ? 'Evaluating…' : 'Evaluate marks'}</button></div>
      </>}
    </section>

    {evaluation && <section className="academic-card academic-summary-card">
      <div className="academic-section-heading">
        <div><h3><BarChart3 size={18}/> Evaluation summary</h3><p>Course-level results based on the current marks register and saved assessment weights. This is a descriptive summary, not an AI-generated diagnosis.</p></div>
      </div>
      <div className="academic-summary-grid">
        <article className="academic-summary-metric"><span><Users size={16}/> Students</span><strong>{evaluation.summary.student_count}</strong><small>{evaluation.summary.evaluated_count} with an available score</small></article>
        <article className="academic-summary-metric"><span><TrendingUp size={16}/> Class average</span><strong>{evaluation.summary.class_average_percentage == null ? '—' : `${evaluation.summary.class_average_percentage.toFixed(2)}%`}</strong><small>Includes provisional scores</small></article>
        <article className="academic-summary-metric"><span><CheckCircle2 size={16}/> Pass rate</span><strong>{evaluation.summary.pass_rate == null ? '—' : `${evaluation.summary.pass_rate.toFixed(1)}%`}</strong><small>Among complete results only</small></article>
        <article className="academic-summary-metric"><span><AlertTriangle size={16}/> Provisional</span><strong>{evaluation.summary.provisional_count}</strong><small>{evaluation.summary.not_assessed_count} not assessed</small></article>
      </div>
      <div className="academic-summary-secondary">
        <div><span>Complete-results average</span><strong>{evaluation.summary.complete_average_percentage == null ? '—' : `${evaluation.summary.complete_average_percentage.toFixed(2)}%`}</strong></div>
        <div><span>Highest score</span><strong>{evaluation.summary.highest_percentage == null ? '—' : `${evaluation.summary.highest_percentage.toFixed(2)}%`}</strong></div>
        <div><span>Lowest score</span><strong>{evaluation.summary.lowest_percentage == null ? '—' : `${evaluation.summary.lowest_percentage.toFixed(2)}%`}</strong></div>
        <div><span>Pass / fail</span><strong>{evaluation.summary.pass_count} / {evaluation.summary.fail_count}</strong></div>
      </div>
      <h4 className="academic-summary-subtitle">Assessment-wise performance</h4>
      <div className="academic-summary-table-wrap"><table className="academic-table academic-summary-table">
        <thead><tr><th>Assessment</th><th>Weight</th><th>Average score</th><th>Students with marks</th><th>Performance</th></tr></thead>
        <tbody>{evaluation.summary.assessment_summary.map(item => <tr key={item.assessment}>
          <td><strong>{item.name}</strong></td><td>{item.weight}%</td>
          <td>{item.average_percentage == null ? '—' : `${item.average_percentage.toFixed(1)}%`}</td>
          <td>{item.students_with_marks} / {evaluation.summary.student_count}</td>
          <td><div className="academic-performance-track"><span style={{ width: `${Math.max(0, Math.min(100, item.average_percentage ?? 0))}%` }}/></div></td>
        </tr>)}</tbody>
      </table></div>
      <p className="academic-summary-footnote">Pass rate excludes provisional and not-assessed students. Assessment averages use only students who have a mark for that assessment. Re-evaluate after editing marks or uploading another file to refresh this summary.</p>
    </section>}
  </div>
}
