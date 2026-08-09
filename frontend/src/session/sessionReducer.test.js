import { describe, expect, it } from 'vitest'
import { INITIAL_STATE, score, sessionReducer } from './sessionReducer.js'

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

  it('records a failed job and transitions out of the creating flow', () => {
    const state = sessionReducer(pending('Black holes'), {
      type: 'poll',
      payload: { job_id: 'abc123', topic: 'Black holes', status: 'failed', questions: [], error: 'no article found' },
    })
    expect(state.phase).toBe('failed')
    expect(state.status).toBe('failed')
    expect(state.error).toBe('no article found')
    expect(state.topic).toBe('Black holes')
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

function aQuestion(i) {
  return {
    section_index: i,
    question: `What about item ${i}?`,
    options: ['Alpha', 'Beta', 'Gamma', 'Delta'].map((o) => `${o} ${i}`),
    correct_answer: `Beta ${i}`,
    source_url: `https://en.wikipedia.org/wiki/Item_${i}`,
  }
}

function startPlay(questionCount, status = 'completed') {
  const questions = Array.from({ length: questionCount }, (_, i) => aQuestion(i))
  let state = sessionReducer(INITIAL_STATE, { type: 'create', topic: 'Black holes' })
  state = sessionReducer(state, {
    type: 'poll',
    payload: { job_id: 'abc123', topic: 'Black holes', status, questions, error: null },
  })
  expect(state.phase).toBe('playing')
  return state
}

describe('playing start', () => {
  it('transitions into playing as soon as questions exist', () => {
    const state = startPlay(3)
    expect(state.currentIndex).toBe(0)
    expect(state.questions).toHaveLength(3)
    expect(state.answers).toEqual({})
  })
})

describe('option shuffling', () => {
  it.each([0, 1, 2])('shuffles options for question %i into a permutation', (i) => {
    const state = startPlay(3)
    const order = state.optionOrder[i]
    expect(order).toHaveLength(4)
    expect([...order].sort()).toEqual([...state.questions[i].options].sort())
  })

  it('starts from a different order than the backend-provided one at least once', () => {
    for (let attempt = 0; attempt < 20; attempt += 1) {
      const state = startPlay(3)
      if (state.optionOrder[0].join() !== state.questions[0].options.join()) return
    }
    throw new Error('options were never shuffled in 20 tries')
  })

  it('keeps the shuffled order stable across prev/back navigation', () => {
    let state = startPlay(3)
    const firstOrder = state.optionOrder[0]
    state = sessionReducer(state, { type: 'answer', index: 0, option: state.optionOrder[0][0] })
    state = sessionReducer(state, { type: 'next' })
    state = sessionReducer(state, { type: 'prev' })
    expect(state.optionOrder[0]).toEqual(firstOrder)
  })

  it('does not reshuffle or duplicate questions already in the queue on a later poll', () => {
    let state = startPlay(3)
    const firstOrder = state.optionOrder[0]
    const fullList = [aQuestion(0), aQuestion(1), aQuestion(2)]
    state = sessionReducer(state, {
      type: 'poll',
      payload: { job_id: 'abc123', topic: 'Black holes', status: 'completed', questions: fullList, error: null },
    })
    expect(state.questions).toHaveLength(3)
    expect(state.optionOrder[0]).toEqual(firstOrder)
  })
})

describe('answer', () => {
  it('records exactly one option for the current question', () => {
    let state = startPlay(3)
    const chosen = state.optionOrder[0][2]
    state = sessionReducer(state, { type: 'answer', index: 0, option: chosen })
    expect(state.answers[0]).toBe(chosen)
  })

  it('lets a later answer replace an earlier one (change until the end)', () => {
    let state = startPlay(3)
    state = sessionReducer(state, { type: 'answer', index: 0, option: state.optionOrder[0][0] })
    const secondPick = state.optionOrder[0][1]
    state = sessionReducer(state, { type: 'answer', index: 0, option: secondPick })
    expect(state.answers[0]).toBe(secondPick)
  })

  it('ignores answers for questions outside the set', () => {
    let state = startPlay(3)
    state = sessionReducer(state, { type: 'answer', index: 5, option: 'Nope' })
    expect(state.answers).toEqual({})
  })

  it('keeps the currentIndex stationary while answering', () => {
    let state = startPlay(3)
    state = sessionReducer(state, { type: 'answer', index: 0, option: state.optionOrder[0][0] })
    expect(state.currentIndex).toBe(0)
  })
})

describe('next / prev', () => {
  it('next is a no-op until the current question is answered', () => {
    let state = startPlay(3)
    state = sessionReducer(state, { type: 'next' })
    expect(state.currentIndex).toBe(0)
  })

  it('next advances to the next question once answered', () => {
    let state = startPlay(3)
    state = sessionReducer(state, { type: 'answer', index: 0, option: state.optionOrder[0][0] })
    state = sessionReducer(state, { type: 'next' })
    expect(state.currentIndex).toBe(1)
  })

  it('prev moves back to earlier questions even when unanswered ahead', () => {
    let state = startPlay(3)
    state = sessionReducer(state, { type: 'answer', index: 0, option: state.optionOrder[0][0] })
    state = sessionReducer(state, { type: 'next' })
    state = sessionReducer(state, { type: 'prev' })
    expect(state.currentIndex).toBe(0)
  })

  it('next does not move past the last known question', () => {
    let state = startPlay(3)
    for (const i of [0, 1]) {
      state = sessionReducer(state, { type: 'answer', index: i, option: state.optionOrder[i][0] })
      state = sessionReducer(state, { type: 'next' })
    }
    state = sessionReducer(state, { type: 'answer', index: 2, option: state.optionOrder[2][0] })
    state = sessionReducer(state, { type: 'next' })
    expect(state.currentIndex).toBe(2)
  })

  it('moves freely through answered and unanswered questions back and forth', () => {
    let state = startPlay(3)
    state = sessionReducer(state, { type: 'answer', index: 0, option: state.optionOrder[0][0] })
    state = sessionReducer(state, { type: 'prev' })
    state = sessionReducer(state, { type: 'next' })
    state = sessionReducer(state, { type: 'answer', index: 1, option: state.optionOrder[1][0] })
    state = sessionReducer(state, { type: 'next' })
    expect(state.currentIndex).toBe(2)
    state = sessionReducer(state, { type: 'prev' })
    expect(state.currentIndex).toBe(1)
    expect(state.answers[1]).toBeDefined()
  })
})

describe('progress over the known set', () => {
  it('exposes an answered count per arrival index that grows as questions are answered', () => {
    let state = startPlay(3)
    state = sessionReducer(state, { type: 'answer', index: 0, option: state.optionOrder[0][0] })
    state = sessionReducer(state, { type: 'next' })
    state = sessionReducer(state, { type: 'answer', index: 1, option: state.optionOrder[1][0] })
    expect(Object.keys(state.answers)).toHaveLength(2)
    expect(state.questions).toHaveLength(3)
  })
})

describe('live merge while the job is running', () => {
  const pollWith = (state, status, questions) =>
    sessionReducer(state, {
      type: 'poll',
      payload: {
        job_id: 'abc123',
        topic: 'Black holes',
        status,
        questions,
        error: null,
      },
    })

  it('appends newly arrived questions at their arrival index without disturbing answered ones', () => {
    let state = startPlay(3, 'running')
    state = sessionReducer(state, { type: 'answer', index: 0, option: state.optionOrder[0][0] })
    state = sessionReducer(state, { type: 'next' })
    const orderBefore = state.optionOrder[0]
    const answerBefore = state.answers[0]
    state = pollWith(
      state,
      'running',
      [aQuestion(0), aQuestion(1), aQuestion(2), aQuestion(3), aQuestion(4)],
    )
    expect(state.questions).toHaveLength(5)
    expect(state.answers[0]).toBe(answerBefore)
    expect(state.optionOrder[0]).toEqual(orderBefore)
    expect(state.currentIndex).toBe(1)
  })

  it('does not advance the player when they are still mid-set', () => {
    let state = startPlay(3, 'running')
    state = sessionReducer(state, { type: 'answer', index: 0, option: state.optionOrder[0][0] })
    state = sessionReducer(state, { type: 'next' })
    state = pollWith(
      state,
      'running',
      [aQuestion(0), aQuestion(1), aQuestion(2), aQuestion(3)],
    )
    expect(state.questions).toHaveLength(4)
    expect(state.currentIndex).toBe(1)
  })

  it('answers can keep being recorded against their stable arrival index after growth', () => {
    let state = startPlay(3, 'running')
    for (const i of [0, 1, 2]) {
      state = sessionReducer(state, { type: 'answer', index: i, option: state.optionOrder[i][0] })
    }
    state = pollWith(
      state,
      'running',
      [aQuestion(0), aQuestion(1), aQuestion(2), aQuestion(3), aQuestion(4)],
    )
    expect(state.questions).toHaveLength(5)
    expect(state.currentIndex).toBe(3)
    state = sessionReducer(state, { type: 'answer', index: 3, option: state.optionOrder[3][0] })
    expect(state.answers[3]).toBe(state.optionOrder[3][0])
  })

  it('records a completed status while the quiz is still being played', () => {
    let state = startPlay(3, 'running')
    state = pollWith(state, 'completed', [aQuestion(0), aQuestion(1), aQuestion(2)])
    expect(state.status).toBe('completed')
    expect(state.phase).toBe('playing')
    expect(state.currentIndex).toBe(0)
  })

  it('surfaces a failed job the same way when it happens mid-play', () => {
    let state = startPlay(3, 'running')
    state = sessionReducer(state, { type: 'answer', index: 0, option: state.optionOrder[0][0] })
    state = sessionReducer(state, {
      type: 'poll',
      payload: {
        job_id: 'abc123',
        topic: 'Black holes',
        status: 'failed',
        questions: [aQuestion(0), aQuestion(1), aQuestion(2)],
        error: 'generation failed',
      },
    })
    expect(state.phase).toBe('failed')
    expect(state.status).toBe('failed')
    expect(state.error).toBe('generation failed')
    expect(state.questions).toHaveLength(3)
  })

  it('ignores further polls and player input once a job has failed', () => {
    let state = startPlay(3, 'running')
    state = pollWith(state, 'failed', [])
    const failed = state
    expect(sessionReducer(failed, { type: 'answer', index: 0, option: 'Nope' })).toBe(failed)
    expect(sessionReducer(failed, { type: 'next' })).toBe(failed)
    expect(sessionReducer(failed, { type: 'prev' })).toBe(failed)
    expect(sessionReducer(failed, { type: 'poll', payload: { job_id: 'abc123', topic: 'Black holes', status: 'running', questions: [], error: null } })).toBe(failed)
  })
})

describe('quiz resolution', () => {
  it('stays playing while a running job has everything answered', () => {
    let state = startPlay(2, 'running')
    for (const i of [0, 1]) {
      state = sessionReducer(state, { type: 'answer', index: i, option: state.optionOrder[i][0] })
    }
    expect(state.phase).toBe('playing')
  })

  it('resolves once every known question of a completed job is answered', () => {
    let state = startPlay(3, 'completed')
    for (const i of [0, 1, 2]) {
      state = sessionReducer(state, { type: 'answer', index: i, option: state.optionOrder[i][0] })
    }
    expect(state.phase).toBe('finished')
  })

  it('resolves when a poll delivers a completed job with everything already answered', () => {
    let state = startPlay(2, 'running')
    for (const i of [0, 1]) {
      state = sessionReducer(state, { type: 'answer', index: i, option: state.optionOrder[i][0] })
    }
    state = sessionReducer(state, {
      type: 'poll',
      payload: {
        job_id: 'abc123',
        topic: 'Black holes',
        status: 'completed',
        questions: [aQuestion(0), aQuestion(1)],
        error: null,
      },
    })
    expect(state.phase).toBe('finished')
  })

  it('answers cannot change once the quiz has resolved', () => {
    let state = startPlay(2, 'completed')
    state = sessionReducer(state, { type: 'answer', index: 0, option: state.optionOrder[0][0] })
    state = sessionReducer(state, { type: 'answer', index: 1, option: state.optionOrder[1][0] })
    const resolved = state
    state = sessionReducer(state, { type: 'answer', index: 0, option: state.optionOrder[0][1] })
    expect(state).toBe(resolved)
  })
})

describe('score', () => {
  function finished(state, targets) {
    for (let i = 0; i < state.questions.length; i += 1) {
      state = sessionReducer(state, {
        type: 'answer',
        index: i,
        option: targets[i],
      })
    }
    return state
  }

  it('scores all correct when every answer matches the correct answer', () => {
    let state = startPlay(3, 'completed')
    state = finished(state, state.questions.map((q) => q.correct_answer))
    expect(score(state)).toEqual({ correct: 3, total: 3, percent: 100 })
  })

  it('scores zero when no answer matches the correct answer', () => {
    let state = startPlay(3, 'completed')
    const allWrong = state.questions.map((q) => q.options.find((o) => o !== q.correct_answer))
    state = finished(state, allWrong)
    expect(score(state)).toEqual({ correct: 0, total: 3, percent: 0 })
  })

  it('computes a rounded percentage for partial credit', () => {
    let state = startPlay(3, 'completed')
    const correct = state.questions.map((q) => q.correct_answer)
    correct[1] = state.optionOrder[1].find((o) => o !== correct[1])
    state = finished(state, correct)
    expect(score(state)).toEqual({ correct: 2, total: 3, percent: 67 })
  })

  it('returns a zeroed result on a session with no questions', () => {
    expect(score(INITIAL_STATE)).toEqual({ correct: 0, total: 0, percent: 0 })
  })
})
