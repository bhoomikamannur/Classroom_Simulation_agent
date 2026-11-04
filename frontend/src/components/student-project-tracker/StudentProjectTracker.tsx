import { ProjectTrackerCore } from '../ProjectTrackerCore'

type Props = { courseId?: string; onBack?: () => void }

export function StudentProjectTracker({ courseId, onBack }: Props) {
  return <ProjectTrackerCore courseId={courseId} role="student" onBack={onBack} />
}
