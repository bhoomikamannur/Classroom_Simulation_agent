import { useEffect, useState } from 'react'
import { ArrowRight, CalendarDays, ClipboardList, FolderKanban, LoaderCircle } from 'lucide-react'
import { apiFetch } from '../../services/api'

type WidgetProject = {
  student_project_id: string
  course_id: string
  title: string
  status: string
  proposal_status: string
  milestones?: { milestone_id: string; title: string; due_date: string; is_deleted?: boolean }[]
}

async function read<T>(response: Response): Promise<T> {
  const data = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Could not load project.')
  return data as T
}

export function StudentProjectWidget({ courseId, onOpen }: { courseId: string; onOpen: () => void }) {
  const [project, setProject] = useState<WidgetProject | null>(null)
  const [nextCheckpoint, setNextCheckpoint] = useState<NonNullable<WidgetProject['milestones']>[number] | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    apiFetch('/api/project-tracker/mine')
      .then((response) => read<{ projects: WidgetProject[] }>(response))
      .then((data) => {
        if (!active) return
        const assigned = data.projects.find((item) => item.course_id === courseId) ?? null
        setProject(assigned)
        const upcoming = assigned?.milestones
          ?.filter((item) => !item.is_deleted && new Date(item.due_date).getTime() >= Date.now())
          .sort((a, b) => new Date(a.due_date).getTime() - new Date(b.due_date).getTime())[0] ?? null
        setNextCheckpoint(upcoming)
      })
      .catch((reason) => { if (active) setError(reason instanceof Error ? reason.message : 'Could not load project details.') })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [courseId])

  return <section className="student-project-widget" aria-label="Course project tracker">
    <div className="student-project-widget-icon"><FolderKanban size={25}/></div>
    <div className="student-project-widget-content">
      <span className="panel-kicker">YOUR COURSE PROJECT</span>
      <h2>{loading ? 'Loading your project…' : project?.title ?? 'Project Tracker'}</h2>
      <p>{error || (project ? 'Your individual workspace is ready. Submit your proposal, checkpoint updates and deliverables, and review professor feedback.' : 'Open your project workspace to check whether a project has been assigned to you.')}</p>
      {project && <div className="student-project-widget-meta">
        <span><ClipboardList size={14}/> {project.proposal_status.replaceAll('_', ' ')}</span>
        {nextCheckpoint && <span><CalendarDays size={14}/> Next: {nextCheckpoint.title} · {new Date(nextCheckpoint.due_date).toLocaleDateString()}</span>}
      </div>}
    </div>
    <button type="button" className="primary-button student-project-widget-action" onClick={onOpen} disabled={loading}>
      {loading ? <LoaderCircle className="spin" size={16}/> : <>Open My Project <ArrowRight size={16}/></>}
    </button>
  </section>
}
