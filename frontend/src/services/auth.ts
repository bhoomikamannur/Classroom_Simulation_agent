import { apiFetch } from './api'
import type { AuthUser } from '../types'

const TOKEN_KEY = 'classroom_ai_access_token'

async function readResponse(response: Response) {
  const data = await response.json().catch(() => ({}))
  if (!response.ok) {
    throw new Error(typeof data.detail === 'string' ? data.detail : 'The request could not be completed.')
  }
  return data
}

export async function login(email: string, password: string): Promise<AuthUser> {
  const response = await apiFetch('/api/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  })
  const data = await readResponse(response)
  const token = data.access_token ?? data.token
  if (typeof token !== 'string' || !token) {
    throw new Error('Login response did not contain an access token. Check the backend login response field.')
  }
  localStorage.setItem(TOKEN_KEY, token)
  return getCurrentUser()
}

export async function register(payload: {
  email: string
  password: string
  role: 'student' | 'professor'
  roll_number?: string
  display_name?: string
  professor_registration_code?: string
}) {
  const response = await apiFetch('/api/auth/register', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  return readResponse(response)
}

export async function getCurrentUser(): Promise<AuthUser> {
  if (!localStorage.getItem(TOKEN_KEY)) throw new Error('No active session.')
  const response = await apiFetch('/api/auth/me')
  const data = await readResponse(response)
  if (typeof data.email !== 'string' || !['student', 'professor'].includes(data.role)) {
    throw new Error('The server returned an invalid user profile.')
  }
  return data as AuthUser
}

export function logout() {
  localStorage.removeItem(TOKEN_KEY)
}
