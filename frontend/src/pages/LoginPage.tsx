import { useState, type FormEvent } from 'react'
import { BrainCircuit, LoaderCircle, LockKeyhole, Mail } from 'lucide-react'
import { login } from '../services/auth'
import type { AuthUser } from '../types'

type Props = {
  onAuthenticated: (user: AuthUser) => void
  onShowRegister: () => void
}

export function LoginPage({ onAuthenticated, onShowRegister }: Props) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function submit(event: FormEvent) {
    event.preventDefault()
    setError('')
    setLoading(true)
    try {
      onAuthenticated(await login(email.trim(), password))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to log in.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="auth-page">
      <section className="auth-card">
        <div className="auth-brand-mark"><BrainCircuit size={28} /></div>
        <p className="auth-eyebrow">CLASSROOM AI</p>
        <h1>Welcome back</h1>
        <p className="auth-subtitle">Sign in to continue to your learning workspace.</p>
        <form onSubmit={submit} className="auth-form">
          <label htmlFor="login-email">Email address</label>
          <div className="auth-input-wrap"><Mail size={17} /><input id="login-email" type="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="you@example.com" autoComplete="email" required /></div>
          <label htmlFor="login-password">Password</label>
          <div className="auth-input-wrap"><LockKeyhole size={17} /><input id="login-password" type="password" value={password} onChange={e => setPassword(e.target.value)} placeholder="Enter your password" autoComplete="current-password" required /></div>
          {error && <p className="auth-error" role="alert">{error}</p>}
          <button className="auth-submit" type="submit" disabled={loading}>{loading ? <><LoaderCircle className="spin" size={17} /> Signing in…</> : 'Sign in'}</button>
        </form>
        <p className="auth-switch">Don't have an account? <button type="button" onClick={onShowRegister}>Create account</button></p>
      </section>
      <p className="auth-footnote">An intelligent classroom. Connected teaching and learning.</p>
    </main>
  )
}
