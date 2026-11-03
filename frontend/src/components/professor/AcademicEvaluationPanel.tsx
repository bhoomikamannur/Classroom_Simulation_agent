import { useEffect, useState } from 'react'
import { AlertCircle, RefreshCw, Upload, Trash2, ChevronDown, ChevronUp, Pencil } from 'lucide-react'
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
  const visibleRows = expanded ? (register?.students ?? []) : (register?.students ?? []).slice(0, 10)

  async function refreshRegister() {
    const data = await readJson<Register>(await apiFetch(`/api/academic-evaluation/register/${encodeURIComponent(courseId)}`))
    setRegister(data)
  }

  async function refreshUploads() {
    const data = await readJson<{ uploads: UploadRecord[] }>(await apiFetch(`/api/academic-evaluation/uploads/${encodeURIComponent(courseId)}`))
    setUploads(data.uploads ?? [])
  }

  async function refreshAll() {
    setError('')
    try { await Promise.all([refreshRegister(), refreshUploads()]) }
    catch (e) { setError(e instanceof Error ? e.message : 'Could not load academic marks.') }
  }

  useEffect(() => {
    setRegister(null); setUploads([]); setError(''); setMessage(''); setExpanded(false)
    if (courseId) void refreshAll()
    // refreshAll is intentionally scoped to the selected course.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [courseId])

  async function uploadMarks() {
    if (!marksFile) return
    setBusy('upload'); setError(''); setMessage('')
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
    setBusy(`delete:${upload.upload_id}`); setError(''); setMessage('')
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
    setBusy('edit'); setError(''); setMessage('')
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
        <div className="academic-table-wrap"><table className="academic-table"><thead><tr><th>Student roll number</th>{assessmentEntries.map(([key, name]) => <th key={key}>{name}</th>)}</tr></thead>
          <tbody>{visibleRows.map(student => <tr key={student.student_id}><td>{student.display_id || student.student_id}</td>{assessmentEntries.map(([key]) => {
            const value = student.assessments?.[key] ?? null
            const maximum = student.assessment_maximums?.[key]
            return <td key={key}><button type="button" className="academic-mark-cell" title="Edit mark" disabled={busy === 'edit'} onClick={() => void editMark(student, key, value)}>{value == null ? '—' : value}{maximum != null ? <small className="academic-mark-maximum"> / {maximum}</small> : null}<Pencil size={11}/></button></td>
          })}</tr>)}</tbody>
        </table></div>
        {register.students.length > 10 && <button type="button" className="secondary-button academic-expand-button" onClick={() => setExpanded(value => !value)}>{expanded ? <><ChevronUp size={16}/> View less</> : <><ChevronDown size={16}/> View all {register.students.length} students</>}</button>}
        {assessmentEntries.length === 0 && <p>No assessment marks have been uploaded yet.</p>}
      </>}
    </section>
  </div>
}
