import { useState, type FormEvent } from 'react'
import { BrainCircuit, LoaderCircle, LockKeyhole, Mail, UserRound } from 'lucide-react'
import { register } from '../services/auth'

type Props = { onRegistered: () => void; onShowLogin: () => void }

export function RegisterPage({ onRegistered, onShowLogin }: Props) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [rollNumber, setRollNumber] = useState('')
  const [role, setRole] = useState<'student' | 'professor'>('student')
  const [professorCode, setProfessorCode] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function submit(event: FormEvent) {
    event.preventDefault()
    setError('')
    setLoading(true)
    try {
      await register({
        email: email.trim(), password, role,
        ...(role === 'student' ? { roll_number: rollNumber.trim().toLowerCase() } : {}),
        ...(role === 'professor' ? { professor_registration_code: professorCode } : {}),
      })
      onRegistered()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to create your account.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="auth-page">
      <section className="auth-card">
        <div className="auth-brand-mark"><BrainCircuit size={28} /></div>
        <p className="auth-eyebrow">CLASSROOM AI</p>
        <h1>Create your account</h1>
        <p className="auth-subtitle">Register as a student or professor.</p>
        <form onSubmit={submit} className="auth-form">
          <label>Account type</label>
          <div className="auth-role-options">
            <label><input type="radio" name="role" checked={role === 'student'} onChange={() => setRole('student')} /> Student</label>
            <label><input type="radio" name="role" checked={role === 'professor'} onChange={() => setRole('professor')} /> Professor</label>
          </div>
          {role === 'student' && <>
            <label htmlFor="register-roll-number">Student roll number</label>
            <div className="auth-input-wrap"><UserRound size={17} /><input id="register-roll-number" value={rollNumber} onChange={e => setRollNumber(e.target.value)} placeholder="e.g. 23bcs000" minLength={3} maxLength={20} pattern="[A-Za-z0-9][A-Za-z0-9-]{2,19}" autoComplete="off" required /></div>
          </>}
          <label htmlFor="register-email">Email address</label>
          <div className="auth-input-wrap"><Mail size={17} /><input id="register-email" type="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="you@example.com" autoComplete="email" required /></div>
          <label htmlFor="register-password">Password</label>
          <div className="auth-input-wrap"><LockKeyhole size={17} /><input id="register-password" type="password" value={password} onChange={e => setPassword(e.target.value)} placeholder="At least 8 characters" minLength={8} maxLength={72} autoComplete="new-password" required /></div>
          {role === 'professor' && <>
            <label htmlFor="professor-code">Professor registration code</label>
            <div className="auth-input-wrap"><UserRound size={17} /><input id="professor-code" type="password" value={professorCode} onChange={e => setProfessorCode(e.target.value)} placeholder="Enter registration code" required /></div>
          </>}
          {error && <p className="auth-error" role="alert">{error}</p>}
          <button className="auth-submit" type="submit" disabled={loading}>{loading ? <><LoaderCircle className="spin" size={17} /> Creating account…</> : 'Create account'}</button>
        </form>
        <p className="auth-switch">Already registered? <button type="button" onClick={onShowLogin}>Sign in</button></p>
      </section>
      <p className="auth-footnote">An intelligent classroom. Connected teaching and learning.</p>
    </main>
  )
}
