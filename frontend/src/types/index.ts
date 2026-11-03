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
