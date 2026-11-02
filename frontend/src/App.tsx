import { useRef, useState, useEffect } from 'react'
import { BrainCircuit, LoaderCircle } from 'lucide-react'
import './App.css'
import './styles/Auth.css'
import './styles/components.css'
import { ProfessorDashboard } from './pages/ProfessorDashboard'
import { StudentDashboard } from './pages/StudentDashboard'
import { LoginPage } from './pages/LoginPage'
import { RegisterPage } from './pages/RegisterPage'
import { apiFetch } from './services/api'
import { useTutorChats } from './hooks/useTutorChats'
import { getCurrentUser, logout as clearAuth } from './services/auth'
import type { AuthUser, Role, UploadResult } from './types'

function App() {
  const [role, setRole] = useState<Role>(null)
  const [authMode, setAuthMode] = useState<'login' | 'register'>('login')
  const [authChecking, setAuthChecking] = useState(true)
  const [currentUser, setCurrentUser] = useState<AuthUser | null>(null)
  const [selectedCourseId, setSelectedCourseId] = useState('')
  
  useEffect(() => {
    let active = true
    getCurrentUser()
      .then((user) => {
        if (!active) return
        setCurrentUser(user)
        setRole(user.role === 'professor' ? 'teacher' : 'student')
      })
      .catch(() => {
        clearAuth()
        if (active) {
          setCurrentUser(null)
          setRole(null)
        }
      })
      .finally(() => {
        if (active) setAuthChecking(false)
      })
    return () => { active = false }
  }, [])

  function handleAuthenticated(user: AuthUser) {
    setSelectedCourseId('')
    setCurrentUser(user)
    setRole(user.role === 'professor' ? 'teacher' : 'student')
  }

  function handleLogout() {
    clearAuth()
    setCurrentUser(null)
    setSelectedCourseId('')
    setRole(null)
    setAuthMode('login')
    setSelectedFile(null)
    setUploadError('')
    setUploadResult(null)
  }
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState('')
  const [uploadResult, setUploadResult] = useState<UploadResult | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  
  

  const tutorChats = useTutorChats(
    currentUser?.role === 'student' ? currentUser.user_id : null,
    selectedCourseId || null,
  )

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

  async function uploadDocument(courseId: string) {
    if (!selectedFile || uploading || !courseId) return

    setUploading(true)
    setUploadError('')
    setUploadResult(null)

    const formData = new FormData()
    formData.append('file', selectedFile)
    formData.append('course_id', courseId)

    try {
      const response = await apiFetch('/api/documents/upload', {
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

      setUploadResult((data.document ?? data) as UploadResult)
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
        <a className="brand" href="#dashboard">
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
          {role && <button type="button" className="auth-logout-button" onClick={handleLogout}>Log out</button>}
        </div>
      </header>

      {authChecking ? (
        <section className="auth-loading" aria-live="polite">
          <LoaderCircle className="spin" size={24} />
          <span>Checking your session…</span>
        </section>
      ) : !role ? (
        authMode === 'login' ? (
          <LoginPage onAuthenticated={handleAuthenticated} onShowRegister={() => setAuthMode('register')} />
        ) : (
          <RegisterPage onRegistered={() => setAuthMode('login')} onShowLogin={() => setAuthMode('login')} />
        )
      ) : null}

      {role === 'teacher' && (
        <ProfessorDashboard
          currentUser={currentUser}
          onLogout={handleLogout}
          selectedFile={selectedFile}
          fileInputRef={fileInputRef}
          uploading={uploading}
          uploadError={uploadError}
          uploadResult={uploadResult}
          onChooseFile={chooseFile}
          onUpload={(courseId) => void uploadDocument(courseId)}
          onDismissError={() => setUploadError('')}
          onDismissResult={() => setUploadResult(null)}
        />
      )}

      
      {role === 'student' && (
        <StudentDashboard
          currentUser={currentUser}
          onLogout={handleLogout}
          selectedCourseId={selectedCourseId}
          onSelectCourse={setSelectedCourseId}
          savedChats={tutorChats.savedChats}
          activeChatId={tutorChats.activeChatId}
          chatMessages={tutorChats.chatMessages}
          chatLoading={tutorChats.chatLoading}
          chatError={tutorChats.chatError}
          chatInput={tutorChats.chatInput}
          onStartNewChat={tutorChats.startNewChat}
          onOpenChat={tutorChats.openChat}
          onChatInputChange={tutorChats.setChatInput}
          onSendMessage={() => void tutorChats.sendTutorMessage()}
        />
      )}

      <footer className="app-footer">
        <span>Classroom AI · Agentic Learning System</span>
        <span>Designed for better learning outcomes</span>
      </footer>
    </main>
  )
}

export default App
