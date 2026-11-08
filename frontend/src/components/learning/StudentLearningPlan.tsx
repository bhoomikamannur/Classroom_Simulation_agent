import { useEffect, useRef, useState } from 'react'
import { BookOpenCheck, CheckCircle2, ClipboardCheck, LoaderCircle, RefreshCw } from 'lucide-react'
import { apiFetch } from '../../services/api'

type Topic = { topic_id: string; title: string; status: string; mastery_score?: number | null }
type Question = { question_id: string; topic_id: string; topic_title: string; question: string; options: string[] }
type Unit = { unit_id: string; title: string; start_week: number; end_week: number; topics: Topic[]; revision_topics?: { topic_id: string; title: string; mastery_score: number }[]; early_completion?: boolean; behind_schedule_topics?: string[]; assessment_status?: string; assessment_topics_ready?: number; assessment_topics_total?: number; revision_week?: number | null }
type Plan = { semester_weeks: number; current_week?: number; units: Unit[]; adaptation_summary?: string }
async function read<T>(response: Response): Promise<T> { const data = await response.json().catch(() => ({})); if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Request failed.'); return data as T }

export function StudentLearningPlan({ courseId }: { courseId: string }) {
  const [plan, setPlan] = useState<Plan | null>(null)
  const [questions, setQuestions] = useState<Question[]>([])
  const [assessmentId, setAssessmentId] = useState('')
  const [answers, setAnswers] = useState<Record<string, number>>({})
  const [result, setResult] = useState<{ score: number; message: string; topics_to_revisit: { title: string; mastery_score: number }[] } | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const assessmentRef = useRef<HTMLElement | null>(null)
  const answeredCount = questions.filter((question) => answers[question.question_id] !== undefined).length
  async function load() { try { const data = await read<{ plan: Plan }>(await apiFetch(`/api/learning-plans/courses/${courseId}/mine`)); setPlan(data.plan); setError('') } catch (e) { setError(e instanceof Error ? e.message : 'Could not load learning plan.') } }
  // eslint-disable-next-line react-hooks/set-state-in-effect, react-hooks/exhaustive-deps
  useEffect(() => { void load() }, [courseId])
  useEffect(() => {
    if (questions.length > 0) {
      window.setTimeout(() => assessmentRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 80)
    }
  }, [questions])
  useEffect(() => {
    if (questions.length === 0) return
    const warnBeforeExit = (event: BeforeUnloadEvent) => { event.preventDefault(); event.returnValue = '' }
    const keepAssessmentOpen = (event: KeyboardEvent) => { if (event.key === 'Escape') event.preventDefault() }
    window.addEventListener('beforeunload', warnBeforeExit)
    window.addEventListener('keydown', keepAssessmentOpen)
    return () => {
      window.removeEventListener('beforeunload', warnBeforeExit)
      window.removeEventListener('keydown', keepAssessmentOpen)
    }
  }, [questions.length])
  async function updateTopic(topicId: string, status: string) { setBusy(true); setError(''); try { await read(await apiFetch(`/api/learning-plans/courses/${courseId}/topics/${topicId}`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ status }) })); await load() } catch (e) { setError(e instanceof Error ? e.message : 'Could not update topic.') } finally { setBusy(false) } }
  async function startAssessment(unit: Unit) { setBusy(true); setError(''); setResult(null); try { const data = await read<{ assessment_id: string; questions: Question[] }>(await apiFetch(`/api/learning-plans/courses/${courseId}/units/${unit.unit_id}/assessment`, { method: 'POST' })); setAssessmentId(data.assessment_id); setQuestions(data.questions); setAnswers({}) } catch (e) { setError(e instanceof Error ? e.message : 'Could not generate assessment.') } finally { setBusy(false) } }
  async function submitAssessment() { setBusy(true); setError(''); try { const data = await read<{ score: number; message: string; topics_to_revisit: { title: string; mastery_score: number }[] }>(await apiFetch(`/api/learning-plans/courses/${courseId}/assessments/${assessmentId}/submit`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ answers }) })); setResult(data); setQuestions([]); await load() } catch (e) { setError(e instanceof Error ? e.message : 'Could not submit assessment.') } finally { setBusy(false) } }

  return <section className="student-learning-plan">
    <div className="student-section-heading"><div><span className="panel-kicker">YOUR ADAPTIVE LEARNING JOURNEY</span><h2>My learning plan</h2><p>Follow the unit timeline at your own pace. Complete topics and take a formative assessment when a unit is finished.</p></div><button className="secondary-button" onClick={() => void load()}><RefreshCw size={14}/> Refresh</button></div>
    {error && <div className="feedback error-feedback">{error}</div>}
    {!plan && !error && <p>Loading your learning plan…</p>}
    {plan && plan.units.map((unit) => {
      const completed = unit.topics.filter((topic) => topic.status === 'completed').length
      const allDone = completed === unit.topics.length
      return <article className="student-learning-unit" key={unit.unit_id}>
        <header><div><span className="panel-kicker">UNIT {plan.units.indexOf(unit) + 1}</span><h3>{unit.title}</h3><p>Target: Weeks {unit.start_week}–{unit.end_week}</p>{unit.revision_week != null && <p>Personalized revision: Week {unit.revision_week}</p>}</div><span className="unit-progress-count">{completed}/{unit.topics.length} topics</span></header>
        <div className="student-topic-checklist">{unit.topics.map((topic) => <label key={topic.topic_id} className={topic.status === 'completed' ? 'topic-done' : ''}><input type="checkbox" checked={topic.status === 'completed'} disabled={busy} onChange={(e) => void updateTopic(topic.topic_id, e.target.checked ? 'completed' : 'not_started')}/><span>{topic.title}</span>{topic.mastery_score != null && <small>{topic.mastery_score}% mastery</small>}</label>)}</div>
        <div className="unit-assessment-action">{allDone ? unit.assessment_status === 'ready' ? <button className="primary-button" disabled={busy} onClick={() => void startAssessment(unit)}><ClipboardCheck size={15}/> Take unit assessment</button> : <span><LoaderCircle size={15} className={unit.assessment_status === 'failed' ? '' : 'spin'}/> {unit.assessment_status === 'failed' ? 'Assessment preparation needs attention. Ask your professor to retry preparation.' : `Assessment is being prepared (${unit.assessment_topics_ready ?? 0}/${unit.assessment_topics_total ?? unit.topics.length} topics). It will be ready here automatically.`}</span> : <span><BookOpenCheck size={15}/> Complete all topics to unlock the unit assessment.</span>}</div>
      </article>
    })}
    {questions.length > 0 && <div className="unit-quiz-backdrop" role="presentation">
      <section className="unit-quiz-panel unit-quiz-modal" ref={assessmentRef} role="dialog" aria-modal="true" aria-labelledby="unit-quiz-title">
        <div className="unit-quiz-heading"><div><span className="panel-kicker">FORMATIVE ASSESSMENT</span><h3 id="unit-quiz-title">Unit assessment</h3><p>This assessment has {questions.length} questions. Your answers are required before submission, and it does not affect your academic grade.</p></div><span className="unit-quiz-count">{answeredCount}/{questions.length} answered</span></div>
        <div className="unit-quiz-progress"><span style={{ width: `${questions.length ? answeredCount / questions.length * 100 : 0}%` }}/></div>
        {questions.map((question, index) => <fieldset key={question.question_id}><legend>{index + 1}. {question.question}</legend><small>{question.topic_title}</small>{question.options.map((option, optionIndex) => <label key={optionIndex}><input type="radio" name={question.question_id} checked={answers[question.question_id] === optionIndex} onChange={() => setAnswers((current) => ({ ...current, [question.question_id]: optionIndex }))}/>{option}</label>)}</fieldset>)}
        <div className="unit-quiz-submit-row"><span>{answeredCount === questions.length ? 'All questions answered. You can submit now.' : `Answer ${questions.length - answeredCount} more question${questions.length - answeredCount === 1 ? '' : 's'} to submit.`}</span><button className="primary-button" disabled={busy || answeredCount !== questions.length} onClick={() => void submitAssessment()}>{busy ? <LoaderCircle className="spin" size={15}/> : <CheckCircle2 size={15}/>} Submit assessment</button></div>
      </section>
    </div>}
    {result && <div className="assessment-result"><strong>Assessment score: {result.score}%</strong><p>{result.message}</p></div>}
  </section>
}
