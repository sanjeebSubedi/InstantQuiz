import { useEffect, useReducer, useState } from 'react'
import { createQuiz, getQuiz } from './api.js'
import { INITIAL_STATE, sessionReducer } from './session/sessionReducer.js'
import { readJobId, writeJobId } from './session/url.js'
import { loadSession, saveSession } from './session/storage.js'

const POLL_INTERVAL_MS = 2000

function init() {
  const jobId = readJobId()
  if (!jobId) return INITIAL_STATE
  const blob = loadSession(jobId)
  return sessionReducer(INITIAL_STATE, { type: 'restore', jobId, topic: blob?.topic })
}

export default function App() {
  const [state, dispatch] = useReducer(sessionReducer, null, init)
  const [topicInput, setTopicInput] = useState('')

  useEffect(() => {
    if (state.phase !== 'creating' || !state.jobId) return
    let stopped = false
    const tick = async () => {
      try {
        const payload = await getQuiz(state.jobId)
        if (!stopped) dispatch({ type: 'poll', payload })
      } catch {
        // Transient poll failures are retried on the next tick.
      }
    }
    tick()
    const id = setInterval(tick, POLL_INTERVAL_MS)
    return () => {
      stopped = true
      clearInterval(id)
    }
  }, [state.phase, state.jobId])

  async function handleSubmit(e) {
    e.preventDefault()
    const topic = topicInput.trim()
    if (!topic || state.phase !== 'idle') return
    dispatch({ type: 'create', topic })
    try {
      const { job_id } = await createQuiz(topic)
      writeJobId(job_id)
      saveSession(job_id, { jobId: job_id, topic })
      dispatch({ type: 'poll', payload: { job_id, status: 'running' } })
    } catch {
      dispatch({ type: 'reset' })
    }
  }

  if (state.phase === 'pending' || state.phase === 'creating') {
    return (
      <main className="creating">
        <h1>Creating quiz</h1>
        {state.topic && <p className="topic">for &ldquo;{state.topic}&rdquo;</p>}
        <p className="hint">
          We are generating your questions. This should only take a few moments.
        </p>
      </main>
    )
  }

  return (
    <main className="landing">
      <h1>Instant Quiz</h1>
      <p className="tagline">A quiz about any topic, generated in moments.</p>
      <form onSubmit={handleSubmit}>
        <label htmlFor="topic">Enter a topic</label>
        <input
          id="topic"
          type="text"
          value={topicInput}
          onChange={(e) => setTopicInput(e.target.value)}
          placeholder="e.g. Black holes"
          autoFocus
        />
        <button type="submit" disabled={!topicInput.trim()}>
          Create quiz
        </button>
      </form>
    </main>
  )
}