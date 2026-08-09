function key(jobId) {
  return `quizSession:${jobId}`
}

export function saveSession(jobId, blob) {
  try {
    window.localStorage.setItem(key(jobId), JSON.stringify(blob))
  } catch {
    // Storage unavailable (private mode, quota); the session just won't survive a refresh.
  }
}

export function loadSession(jobId) {
  try {
    const raw = window.localStorage.getItem(key(jobId))
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}