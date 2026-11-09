const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '')

function resolveApiInput(input: RequestInfo | URL): RequestInfo | URL {
  if (!API_BASE_URL || typeof input !== 'string' || !input.startsWith('/api/')) return input
  return `${API_BASE_URL}${input.replace(/^\/api/, '')}`
}

export async function apiFetch(input: RequestInfo | URL, init: RequestInit = {}) {
  const headers = new Headers(init.headers)
  const token = localStorage.getItem('classroom_ai_access_token')
  if (token) headers.set('Authorization', `Bearer ${token}`)
  return fetch(resolveApiInput(input), { ...init, headers })
}


async function fetchDocumentBlob(documentId: string, action: 'view' | 'download') {
  const response = await apiFetch(
    `/api/documents/${encodeURIComponent(documentId)}/${action}`,
  )
  if (!response.ok) {
    const data = await response.json().catch(() => ({}))
    throw new Error(typeof data.detail === 'string' ? data.detail : 'Could not retrieve document.')
  }
  return response.blob()
}

export async function openCourseDocument(documentId: string) {
  // Open the tab synchronously from the click handler to avoid popup blockers.
  const tab = window.open('', '_blank')
  try {
    const blob = await fetchDocumentBlob(documentId, 'view')
    const objectUrl = URL.createObjectURL(blob)
    if (tab) {
      tab.location.href = objectUrl
      window.setTimeout(() => URL.revokeObjectURL(objectUrl), 60_000)
    } else {
      URL.revokeObjectURL(objectUrl)
      throw new Error('Your browser blocked the preview tab. Allow pop-ups and try again.')
    }
  } catch (error) {
    tab?.close()
    throw error
  }
}

export async function downloadCourseDocument(documentId: string, filename: string) {
  const blob = await fetchDocumentBlob(documentId, 'download')
  const objectUrl = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = objectUrl
  anchor.download = filename
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  window.setTimeout(() => URL.revokeObjectURL(objectUrl), 60_000)
}
