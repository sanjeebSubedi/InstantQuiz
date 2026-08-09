import { useEffect, useReducer, useState } from 'react'
import { createQuiz, getQuiz } from './api.js'
import { INITIAL_STATE, allAnswered, sessionReducer } from './session/sessionReducer.js'
import { clearJobId, readJobId, writeJobId } from './session/url.js'
import { clearSession, loadSession, saveSession } from './session/storage.js'

const POLL_INTERVAL_MS = 2000

function Playing({ state, dispatch }) {
  const question = state.questions[state.currentIndex]
  const options = state.optionOrder[state.currentIndex]
  const selected = state.answers[state.currentIndex]
  const total = state.questions.length
  const answered = Object.keys(state.answers).length
  const waitingForMore = state.status === 'running' && allAnswered(state.answers, total)

  function answer(option) {
    dispatch({ type: 'answer', index: state.currentIndex, option })
  }

  if (waitingForMore) {
    return (
      <main className="playing">
        <header className="playing-header">
          <p className="progress">
            Answered {answered}/{total}
          </p>
        </header>
        <section className="generating">
          <h2>Generating more questions&hellip;</h2>
          <p>
            You have answered everything available so far. Keep this page open
            while the quiz finishes - new questions will appear here as they are
            generated.
          </p>
        </section>
      </main>
    )
  }

  return (
    <main className="playing">
      <header className="playing-header">
        <p className="progress">
          Answered {answered}/{total}
        </p>
      </header>
      <h1 className="question-text">{question.question}</h1>
      <div className="options" role="radiogroup" aria-label="Options">
        {options.map((option) => (
          <button
            key={option}
            type="button"
            role="radio"
            aria-checked={option === selected}
            className={option === selected ? 'option selected' : 'option'}
            onClick={() => answer(option)}
          >
            {option}
          </button>
        ))}
      </div>
      <footer className="controls">
        <button
          type="button"
          className="secondary"
          onClick={() => dispatch({ type: 'prev' })}
          disabled={state.currentIndex === 0}
        >
          Prev
        </button>
        <button
          type="button"
          onClick={() => dispatch({ type: 'next' })}
          disabled={selected === undefined || state.currentIndex >= total - 1}
        >
          Next
        </button>
      </footer>
    </main>
  )
}

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
    if (!state.jobId || state.status !== 'running') return
    if (state.phase !== 'creating' && state.phase !== 'playing') return
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
  }, [state.phase, state.jobId, state.status])

  async function startJob(topic) {
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

  function handleSubmit(e) {
    e.preventDefault()
    const topic = topicInput.trim()
    if (!topic || state.phase !== 'idle') return
    startJob(topic)
  }

  function abandonSession() {
    clearJobId()
    if (state.jobId) clearSession(state.jobId)
  }

  function retrySameTopic() {
    if (state.phase !== 'failed' || !state.topic) return
    abandonSession()
    startJob(state.topic)
  }

  function newTopic() {
    if (state.phase !== 'failed') return
    abandonSession()
    setTopicInput('')
    dispatch({ type: 'reset' })
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

  if (state.phase === 'failed') {
    return (
      <main className="failed">
        <h1>Quiz failed</h1>
        {state.topic && <p className="topic">for &ldquo;{state.topic}&rdquo;</p>}
        <p className="error">{state.error || 'Something went wrong while generating your quiz.'}</p>
        <div className="failed-actions">
          <button type="button" onClick={retrySameTopic}>
            Retry same topic
          </button>
          <button type="button" className="secondary" onClick={newTopic}>
            New topic
          </button>
        </div>
      </main>
    )
  }

  if (state.phase === 'finished') {
    return (
      <main className="finished">
        <h1>Quiz complete</h1>
        {state.topic && <p className="topic">for &ldquo;{state.topic}&rdquo;</p>}
        <p className="hint">
          You answered {Object.keys(state.answers).length} of {state.questions.length} questions.
        </p>
      </main>
    )
  }

  if (state.phase === 'playing') {
    return <Playing state={state} dispatch={dispatch} />
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