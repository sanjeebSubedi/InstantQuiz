import { describe, expect, it } from 'vitest'
import { INITIAL_STATE, sessionReducer } from './sessionReducer.js'

describe('create', () => {
  it('transitions into a pending job state and holds the topic', () => {
    const state = sessionReducer(INITIAL_STATE, { type: 'create', topic: 'Black holes' })
    expect(state.phase).toBe('pending')
    expect(state.topic).toBe('Black holes')
    expect(state.jobId).toBeNull()
  })

  it('rejects empty and whitespace-only topics', () => {
    expect(sessionReducer(INITIAL_STATE, { type: 'create', topic: '' })).toBe(INITIAL_STATE)
    expect(sessionReducer(INITIAL_STATE, { type: 'create', topic: '   ' })).toBe(INITIAL_STATE)
  })
})

describe('poll', () => {
  const pending = (topic) => sessionReducer(INITIAL_STATE, { type: 'create', topic })

  it('moves a pending job into the creating state with the job details', () => {
    const state = sessionReducer(pending('Black holes'), {
      type: 'poll',
      payload: { job_id: 'abc123', topic: 'Black holes', status: 'running', questions: [], error: null },
    })
    expect(state.phase).toBe('creating')
    expect(state.jobId).toBe('abc123')
    expect(state.status).toBe('running')
  })

  it('records a failed job so it can be surfaced later', () => {
    const state = sessionReducer(pending('Black holes'), {
      type: 'poll',
      payload: { job_id: 'abc123', topic: 'Black holes', status: 'failed', questions: [], error: 'no article found' },
    })
    expect(state.status).toBe('failed')
    expect(state.error).toBe('no article found')
  })
})

describe('restore', () => {
  it('resumes a stored job into the creating state', () => {
    const state = sessionReducer(INITIAL_STATE, { type: 'restore', jobId: 'abc123', topic: 'Formula One' })
    expect(state.phase).toBe('creating')
    expect(state.jobId).toBe('abc123')
    expect(state.topic).toBe('Formula One')
  })

  it('ignores restores without a job id', () => {
    expect(sessionReducer(INITIAL_STATE, { type: 'restore', jobId: null })).toBe(INITIAL_STATE)
  })
})