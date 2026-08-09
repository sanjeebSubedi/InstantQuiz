export const INITIAL_STATE = Object.freeze({
  phase: 'idle',
  topic: null,
  jobId: null,
  status: null,
  questions: [],
  error: null,
})

export function createSession(jobId, topic) {
  return {
    phase: 'creating',
    jobId,
    topic: topic || null,
    status: 'running',
    questions: [],
    error: null,
  }
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
      if (state.phase !== 'pending' && state.phase !== 'creating') return state
      const p = event.payload
      return {
        ...state,
        phase: 'creating',
        jobId: p.job_id,
        topic: p.topic ?? state.topic,
        status: p.status,
        questions: p.questions ?? state.questions,
        error: p.error ?? null,
      }
    }
    case 'reset':
      return INITIAL_STATE
    default:
      return state
  }
}