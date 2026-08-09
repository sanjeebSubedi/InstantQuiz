export const INITIAL_STATE = Object.freeze({
  phase: 'idle',
  topic: null,
  jobId: null,
  status: null,
  questions: [],
  optionOrder: {},
  answers: {},
  currentIndex: 0,
  error: null,
})

export function createSession(jobId, topic) {
  return {
    phase: 'creating',
    jobId,
    topic: topic || null,
    status: 'running',
    questions: [],
    optionOrder: {},
    answers: {},
    currentIndex: 0,
    error: null,
  }
}

function shuffle(options) {
  const ordered = [...options]
  for (let i = ordered.length - 1; i > 0; i -= 1) {
    const j = Math.floor(Math.random() * (i + 1))
    ;[ordered[i], ordered[j]] = [ordered[j], ordered[i]]
  }
  return ordered
}

function withShuffledArrivals(state, incoming) {
  const questions = [...state.questions]
  const optionOrder = { ...state.optionOrder }
  let newCount = 0
  incoming.forEach((question, position) => {
    if (position >= questions.length) {
      questions.push(question)
      optionOrder[position] = shuffle(question.options)
      newCount += 1
    }
  })
  if (newCount === 0) return state
  return { ...state, questions, optionOrder }
}

export function sessionReducer(state = INITIAL_STATE, event) {
  switch (event.type) {
    case 'create': {
      const topic = (event.topic ?? '').trim()
      if (!topic) return state
      return { ...INITIAL_STATE, phase: 'pending', topic, status: 'running' }
    }
    case 'restore':
      if (!event.jobId) return state
      return createSession(event.jobId, event.topic)
    case 'poll': {
      if (state.phase !== 'pending' && state.phase !== 'creating' && state.phase !== 'playing') return state
      const p = event.payload
      const incoming = p.questions ?? []
      const merged = withShuffledArrivals(state, incoming)
      const hasQuestions = merged.questions.length > 0
      return {
        ...merged,
        phase: hasQuestions ? 'playing' : 'creating',
        jobId: p.job_id,
        topic: p.topic ?? state.topic,
        status: p.status,
        error: p.error ?? null,
      }
    }
    case 'answer': {
      if (state.phase !== 'playing') return state
      const { index, option } = event
      if (!Number.isInteger(index) || index < 0 || index >= state.questions.length) return state
      return { ...state, answers: { ...state.answers, [index]: option } }
    }
    case 'next': {
      if (state.phase !== 'playing') return state
      if (state.answers[state.currentIndex] === undefined) return state
      if (state.currentIndex >= state.questions.length - 1) return state
      return { ...state, currentIndex: state.currentIndex + 1 }
    }
    case 'prev': {
      if (state.phase !== 'playing' || state.currentIndex <= 0) return state
      return { ...state, currentIndex: state.currentIndex - 1 }
    }
    case 'reset':
      return INITIAL_STATE
    default:
      return state
  }
}