import { useEffect, useState } from 'react'
import { BookOpenCheck, CalendarRange, LoaderCircle, RefreshCw, Sparkles, FileSearch } from 'lucide-react'
import { apiFetch } from '../../services/api'

type Topic = { topic_id: string; title: string }
type Unit = { unit_id: string; title: string; start_week: number; end_week: number; topics: Topic[] }
type Plan = { semester_weeks: number; version: number; units: Unit[] }
type Material = { document_id: string; filename: string; status: string }
type Preparation = { unit_id: string; title: string; status: string; completed_topics: number; total_topics: number; error?: string }

async function read<T>(response: Response): Promise<T> {
  const data = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Request failed.')
  return data as T
}

export function LearningPlanPanel({ courseId }: { courseId: string }) {
  const [weeks, setWeeks] = useState(16)
  const [unitsText, setUnitsText] = useState('Unit 1: Introduction to the subject\nIntroduction\nFundamental concepts\nApplications\n\nUnit 2: Core concepts\nConcept A\nConcept B\nConcept C')
  const [plan, setPlan] = useState<Plan | null>(null)
  const [materials, setMaterials] = useState<Material[]>([])
  const [selectedDocument, setSelectedDocument] = useState('')
  const [extracting, setExtracting] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [preparation, setPreparation] = useState<Preparation[]>([])

  async function load() {
    try { const data = await read<{ plan: Plan }>(await apiFetch(`/api/learning-plans/courses/${courseId}`)); setPlan(data.plan); await loadPreparation() }
    catch (e) { if (!(e instanceof Error && e.message.includes('No lesson plan'))) setError(e instanceof Error ? e.message : 'Could not load plan.') }
  }
  async function loadPreparation() {
    try {
      const data = await read<{ units: Preparation[] }>(await apiFetch(`/api/learning-plans/courses/${courseId}/assessment-preparation`))
      setPreparation(data.units)
    } catch { setPreparation([]) }
  }

  // eslint-disable-next-line react-hooks/set-state-in-effect, react-hooks/exhaustive-deps
  useEffect(() => { void load(); void apiFetch(`/api/documents/course/${courseId}`).then((r) => read<{ documents: Material[] }>(r)).then((d) => setMaterials(d.documents.filter((item) => item.status === 'processed'))).catch(() => setMaterials([])) }, [courseId])

  useEffect(() => {
    if (!preparation.some((item) => item.status === 'queued' || item.status === 'processing')) return
    const timer = window.setInterval(() => { void loadPreparation() }, 4000)
    return () => window.clearInterval(timer)
  }, [preparation, courseId])

  function parseUnits() {
    const blocks = unitsText.split(/\n\s*\n/).map((block) => block.split('\n').map((line) => line.trim()).filter(Boolean)).filter((block) => block.length >= 2)
    return blocks.map((block, index) => ({ title: block[0].replace(/^unit\s*\d+\s*[:.-]\s*/i, '').trim() || `Unit ${index + 1}`, topics: block.slice(1) }))
  }

  async function generate(event: React.FormEvent) {
    event.preventDefault(); setLoading(true); setError(''); setMessage('')
    try {
      const units = parseUnits()
      if (!units.length) throw new Error('Add at least one unit with one or more topics. Separate units with a blank line.')
      const data = await read<{ plan: Plan; enrolled_students_initialized: number }>(await apiFetch(`/api/learning-plans/courses/${courseId}/generate`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ units, semester_weeks: weeks }),
      }))
      setPlan(data.plan); setMessage(`Lesson plan published for ${data.enrolled_students_initialized} enrolled student(s). Assessment question banks are being prepared in the background.`); void loadPreparation()
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not generate lesson plan.') }
    finally { setLoading(false) }
  }

  async function extractSyllabus() {
    if (!selectedDocument) return
    setExtracting(true); setError(''); setMessage('')
    try {
      const data = await read<{ units: { title: string; topics: string[] }[]; filename: string }>(await apiFetch(`/api/learning-plans/courses/${courseId}/extract-syllabus`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ document_id: selectedDocument }),
      }))
      setUnitsText(data.units.map((unit) => [unit.title, ...unit.topics].join('\n')).join('\n\n'))
      setMessage(`Extracted ${data.units.length} units from ${data.filename}. Review the outline and publish it when ready.`)
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not extract syllabus.') }
    finally { setExtracting(false) }
  }

  return <section className="learning-plan-panel">
    <div className="panel-heading"><div><span className="panel-kicker">GOAL-ORIENTED COURSE PLANNING</span><h2>Adaptive lesson plan</h2><p>Define syllabus units and topics. The system creates a common baseline timeline; student progress and assessments drive individual adaptation.</p></div><span className="panel-heading-icon"><CalendarRange size={22}/></span></div>
    <form className="learning-plan-form" onSubmit={generate}>
      <div className="syllabus-extract-row"><label>Extract from uploaded syllabus<select value={selectedDocument} onChange={(e) => setSelectedDocument(e.target.value)}><option value="">Select a processed PDF/PPTX</option>{materials.map((item) => <option value={item.document_id} key={item.document_id}>{item.filename}</option>)}</select></label><button className="secondary-button" type="button" disabled={!selectedDocument || extracting} onClick={() => void extractSyllabus()}>{extracting ? <LoaderCircle className="spin" size={15}/> : <FileSearch size={15}/>} Extract units & topics</button></div>
      <label>Semester duration (weeks)<input type="number" min={2} max={30} value={weeks} onChange={(e) => setWeeks(Number(e.target.value))}/></label>
      <label>Units and topics <textarea rows={10} value={unitsText} onChange={(e) => setUnitsText(e.target.value)} placeholder={'Unit 1: Introduction\nTopic 1\nTopic 2\n\nUnit 2: Core concepts\nTopic 1\nTopic 2'}/></label>
      <small>Format: first line of each block is the unit title; following lines are topics. Leave a blank line between units.</small>
      <button className="primary-button" disabled={loading}>{loading ? <LoaderCircle className="spin" size={16}/> : <Sparkles size={16}/>} {plan ? 'Regenerate baseline plan' : 'Generate and publish lesson plan'}</button>
    </form>
    {error && <div className="feedback error-feedback">{error}</div>}
    {message && <div className="feedback success-feedback">{message}</div>}
    {plan && <div className="lesson-plan-preview">
      <div className="lesson-plan-preview-heading"><div><h3>Assessment preparation</h3><p>Questions are generated in the background and reused by students.</p></div><button className="secondary-button" type="button" onClick={() => void loadPreparation()}><RefreshCw size={14}/> Refresh</button></div>
      <div className="lesson-plan-unit-list">{preparation.map((item) => <article className="lesson-plan-unit" key={item.unit_id}><div><strong>{item.title}</strong><span>{item.status === 'ready' ? 'Ready for students' : item.status === 'failed' ? 'Needs retry' : `Preparing · ${item.completed_topics}/${item.total_topics} topics`}</span></div>{item.error && <small>{item.error}</small>}</article>)}</div>
    </div>}
    {plan && <div className="lesson-plan-preview"><div className="lesson-plan-preview-heading"><div><h3>Published course timeline</h3><p>Version {plan.version} · {plan.semester_weeks} weeks</p></div><button className="secondary-button" type="button" onClick={() => void load()}><RefreshCw size={14}/> Refresh</button></div>
      <div className="lesson-plan-unit-list">{plan.units.map((unit) => <article className="lesson-plan-unit" key={unit.unit_id}><div><strong>{unit.title}</strong><span>Weeks {unit.start_week}–{unit.end_week}</span></div><ul>{unit.topics.map((topic) => <li key={topic.topic_id}>{topic.title}</li>)}</ul></article>)}</div>
      <p className="lesson-plan-note"><BookOpenCheck size={15}/> Students receive the same baseline schedule and maintain their own topic completion and mastery records.</p>
    </div>}
  </section>
}
