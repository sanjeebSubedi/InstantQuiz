import { useState } from 'react'
import { useSession } from './session/useSession.js'
import { Playing } from './views/Playing.jsx'
import { Results } from './views/Results.jsx'

export default function App() {
  const { state, actions } = useSession()
  const [topicInput, setTopicInput] = useState('')

  function handleSubmit(e) {
    e.preventDefault()
    const topic = topicInput.trim()
    if (!topic || state.phase !== 'idle') return
    actions.start(topic)
  }

  function handleNewTopic() {
    setTopicInput('')
    actions.newTopic()
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
          <button type="button" onClick={actions.replay}>
            Retry same topic
          </button>
          <button type="button" className="secondary" onClick={handleNewTopic}>
            New topic
          </button>
        </div>
      </main>
    )
  }

  if (state.phase === 'finished') {
    return <Results state={state} onReplay={actions.replay} onNewTopic={handleNewTopic} />
  }

  if (state.phase === 'playing') {
    return <Playing state={state} actions={actions} />
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