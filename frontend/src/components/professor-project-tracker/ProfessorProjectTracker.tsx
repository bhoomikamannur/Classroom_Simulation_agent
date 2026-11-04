import { ProjectTrackerCore } from '../ProjectTrackerCore'

type Props = { courseId: string; onBack?: () => void }

export function ProfessorProjectTracker({ courseId, onBack }: Props) {
  return <ProjectTrackerCore courseId={courseId} role="professor" onBack={onBack} />
}
