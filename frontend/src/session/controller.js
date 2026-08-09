import * as defaultApi from '../api.js'
import * as defaultStorage from './storage.js'
import * as defaultUrl from './url.js'
import { INITIAL_STATE, sessionReducer } from './sessionReducer.js'

const POLL_INTERVAL_MS = 2000

export function createSessionController({
  api = defaultApi,
  storage = defaultStorage,
  url = defaultUrl,
} = {}) {
  let state
  let timer = null
  const listeners = new Set()

  function getState() {
    return state
  }

  function subscribe(listener) {
    listeners.add(listener)
    return () => listeners.delete(listener)
  }

  function notify() {
    for (const listener of listeners) listener()
  }

  function transition(event, payload) {
    state = sessionReducer(state, { type: event, ...payload })
    if (state.jobId && state.phase !== 'idle') {
      storage.saveSession(state.jobId, state)
    }
    updatePolling()
    notify()
  }

  function shouldPoll() {
    return (
      state.jobId &&
      state.status === 'running' &&
      (state.phase === 'creating' || state.phase === 'playing')
    )
  }

  function tick() {
    if (!state.jobId) return
    api.getQuiz(state.jobId).then(
      (payload) => transition('poll', { payload }),
      () => {
        // Transient poll failures are retried on the next tick.
      },
    )
  }

  function updatePolling() {
    if (shouldPoll()) {
      if (timer === null) {
        tick()
        timer = setInterval(tick, POLL_INTERVAL_MS)
      }
    } else if (timer !== null) {
      clearInterval(timer)
      timer = null
    }
  }

  function abandon() {
    url.clearJobId()
    if (state.jobId) storage.clearSession(state.jobId)
  }

  const actions = {
    start(topic) {
      if (!(topic ?? '').trim()) return
      transition('create', { topic })
      api.createQuiz(topic).then(
        ({ job_id }) => {
          url.writeJobId(job_id)
          transition('poll', { payload: { job_id, status: 'running' } })
        },
        () => transition('reset', {}),
      )
    },
    answer(index, option) {
      transition('answer', { index, option })
    },
    next() {
      transition('next', {})
    },
    prev() {
      transition('prev', {})
    },
    replay() {
      if (!state.topic) return
      abandon()
      actions.start(state.topic)
    },
    newTopic() {
      abandon()
      transition('reset', {})
    },
  }

  const jobId = url.readJobId()
  state = sessionReducer(INITIAL_STATE, {
    type: 'restore',
    jobId,
    blob: jobId ? storage.loadSession(jobId) : null,
  })

  if (shouldPoll()) {
    tick()
    timer = setInterval(tick, POLL_INTERVAL_MS)
  }

  return { getState, subscribe, actions }
}