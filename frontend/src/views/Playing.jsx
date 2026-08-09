import { allAnswered } from '../session/sessionReducer.js'

export function Playing({ state, actions }) {
  const question = state.questions[state.currentIndex]
  const options = state.optionOrder[state.currentIndex]
  const selected = state.answers[state.currentIndex]
  const total = state.questions.length
  const answered = Object.keys(state.answers).length
  const waitingForMore = state.status === 'running' && allAnswered(state.answers, total)

  function answer(option) {
    actions.answer(state.currentIndex, option)
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
          onClick={() => actions.prev()}
          disabled={state.currentIndex === 0}
        >
          Prev
        </button>
        <button
          type="button"
          onClick={() => actions.next()}
          disabled={selected === undefined || state.currentIndex >= total - 1}
        >
          Next
        </button>
      </footer>
    </main>
  )
}