import { score } from '../session/sessionReducer.js'

function ReviewRow({ question, answer, index }) {
  const correct = answer === question.correct_answer
  return (
    <li className="review-row">
      <div className="review-head">
        <span className="review-index">Q{index + 1}</span>
        <span className={`badge ${correct ? 'badge-correct' : 'badge-incorrect'}`}>
          {correct ? 'Correct' : 'Incorrect'}
        </span>
      </div>
      <p className="review-question">{question.question}</p>
      <div className="review-answers">
        <div className="review-answer-col">
          <span className="review-label">Your answer</span>
          <span className={correct ? '' : 'wrong'}>{answer}</span>
        </div>
        <div className="review-answer-col">
          <span className="review-label">Correct answer</span>
          <span className="right">{question.correct_answer}</span>
        </div>
      </div>
      <a className="source-link" href={question.source_url} target="_blank" rel="noreferrer">
        Source article
      </a>
    </li>
  )
}

export function Results({ state, onReplay, onNewTopic }) {
  const { correct, total, percent } = score(state)
  return (
    <main className="results">
      <h1>Quiz complete</h1>
      {state.topic && <p className="topic">for &ldquo;{state.topic}&rdquo;</p>}
      <p className="score">
        {correct}/{total} &middot; {percent}%
      </p>
      <ol className="review-list">
        {state.questions.map((question, index) => (
          <ReviewRow key={index} question={question} answer={state.answers[index]} index={index} />
        ))}
      </ol>
      <div className="results-actions">
        <button type="button" onClick={onReplay}>
          Play again
        </button>
        <button type="button" className="secondary" onClick={onNewTopic}>
          New topic
        </button>
      </div>
    </main>
  )
}