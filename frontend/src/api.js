// Base URL of the quiz backend; empty means same-origin (Vite dev proxy).
// Set at build time via VITE_API_BASE_URL when the backend lives on another origin.
const API_BASE = import.meta.env.VITE_API_BASE_URL ?? ''

const QUIZZES_URL = `${API_BASE}/api/quizzes`

async function request(url, options) {
  const res = await fetch(url, options)
  if (!res.ok) {
    let detail = ''
    try {
      const body = await res.json()
      detail = body.detail ?? body.error ?? ''
    } catch {
      // Non-JSON error body; fall through to the status line.
    }
    throw new Error(detail || `request failed (${res.status})`)
  }
  return res.json()
}

export function createQuiz(topic) {
  return request(QUIZZES_URL, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ topic }),
  })
}

export function getQuiz(jobId) {
  return request(`${QUIZZES_URL}/${jobId}`)
}