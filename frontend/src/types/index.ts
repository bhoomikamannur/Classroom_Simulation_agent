export type Role = 'teacher' | 'student' | null

export type UploadResult = {
  filename: string
  file_type: string
  pages_or_slides_extracted: number
  chunk_count: number
}

export type TutorSource = Record<string, unknown>

export type ChatMessage = {
  id: string
  role: 'user' | 'assistant'
  content: string
  sources?: TutorSource[]
}

export type TutorResponse = {
  answer: string
  sources?: TutorSource[]
}

export type SavedTutorChat = {
  id: string
  title: string
  sessionId: string
  messages: ChatMessage[]
  updatedAt: number
}

export type PerformanceResult = {
  student_id: string
  course_id: string | null
  course_name: string
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

export type InterventionResult = {
  student_id: string
  course_id: string | null
  course_name: string
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

export type PerformanceApiResponse = {
  performance: PerformanceResult
  intervention: InterventionResult | null
  analysis_metadata?: { status?: string; interactions_analyzed?: number; sessions_included?: number; course_id?: string }
}

export type AuthUser = {
  user_id: string
  email: string
  role: 'student' | 'professor'
  roll_number?: string | null
  is_active?: boolean
}

export type AcademicAssessment = {
  name: string
  weight: string
  maximum: string
}

export type AcademicStudentResult = {
  student_id: string
  weighted_percentage: number | null
  pass_status: 'pass' | 'fail' | 'provisional' | 'not_assessed' | string
  is_complete: boolean
  message: string
  missing_assessments: string[]
}

export type AcademicEvaluationResponse = {
  course_id: string
  number_of_students: number
  student_results: AcademicStudentResult[]
  grading_policy?: Record<string, unknown>
}

export type ClassAssessmentStats = {
  mean_percentage: number | null
  median_percentage: number | null
  missing_marks: number
  students_with_marks: number
  mean_raw_marks?: number | null
  median_raw_marks?: number | null
}

export type ClassStudentAssessment = {
  marks: number | null
  maximum_marks: number | null
  percentage: number | null
}

export type ClassStudentSummary = {
  student_id: string
  assessments: Record<string, ClassStudentAssessment>
  descriptive_average_percentage: number | null
  relative_performance: string
}

export type ClassAnalyticsResponse = {
  number_of_students: number
  class_assessments: Record<string, ClassAssessmentStats>
  student_summaries: ClassStudentSummary[]
}
