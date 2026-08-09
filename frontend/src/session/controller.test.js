import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createSessionController } from './controller.js'
import { INITIAL_STATE } from './sessionReducer.js'

function aQuestion(i) {
  return {
    section_index: i,
    question: `What about item ${i}?`,
    options: ['Alpha', 'Beta', 'Gamma', 'Delta'].map((o) => `${o} ${i}`),
    correct_answer: `Beta ${i}`,
    source_url: `https://en.wikipedia.org/wiki/Item_${i}`,
  }
}

function playingBlob(jobId, questions) {
  return {
    phase: 'playing',
    topic: 'Black holes',
    jobId,
    status: 'running',
    questions,
    optionOrder: Object.fromEntries(questions.map((q, i) => [i, [...q.options].reverse()])),
    answers: {},
    currentIndex: 0,
    error: null,
  }
}

function streamOf(jobId, status, questions, error = null) {
  return { job_id: jobId, status, questions, error }
}

function makeFakes() {
  let urlJobId = null
  const store = new Map()
  return {
    api: {
      createQuiz: vi.fn(() => new Promise(() => {})),
      getQuiz: vi.fn(() => new Promise(() => {})),
    },
    url: {
      readJobId: () => urlJobId,
      writeJobId: (id) => {
        urlJobId = id
      },
      clearJobId: () => {
        urlJobId = null
      },
    },
    storage: {
      saveSession: vi.fn((id, blob) => store.set(id, blob)),
      loadSession: (id) => store.get(id) ?? null,
      clearSession: vi.fn((id) => store.delete(id)),
    },
    setUrlJob: (id) => {
      urlJobId = id
    },
    seed: (id, blob) => store.set(id, blob),
    store,
  }
}

function makeController(fakes) {
  return createSessionController({ api: fakes.api, url: fakes.url, storage: fakes.storage })
}

const flush = () => vi.advanceTimersByTimeAsync(0)

describe('createSessionController', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('starts from the idle state when no job is in the url', () => {
    expect(makeController(makeFakes()).getState()).toBe(INITIAL_STATE)
  })

  describe('start', () => {
    it('binds the created job into the url and storage', async () => {
      const f = makeFakes()
      f.api.createQuiz.mockResolvedValue({ job_id: 'j1' })
      const ctl = makeController(f)

      ctl.actions.start('Black holes')
      expect(ctl.getState().phase).toBe('pending')
      expect(ctl.getState().topic).toBe('Black holes')

      await flush()
      const s = ctl.getState()
      expect(s.phase).toBe('creating')
      expect(s.jobId).toBe('j1')
      expect(f.url.readJobId()).toBe('j1')
      expect(f.storage.loadSession('j1')).toMatchObject({ jobId: 'j1', phase: 'creating', topic: 'Black holes' })
    })

    it('resets to idle when job creation fails, leaving nothing behind', async () => {
      const f = makeFakes()
      f.api.createQuiz.mockRejectedValue(new Error('down'))
      const ctl = makeController(f)

      ctl.actions.start('Black holes')
      await flush()

      expect(ctl.getState()).toBe(INITIAL_STATE)
      expect(f.url.readJobId()).toBeNull()
      expect(f.storage.saveSession).not.toHaveBeenCalled()
    })

    it('rejects empty and whitespace-only topics without hitting the api', () => {
      const f = makeFakes()
      const ctl = makeController(f)

      ctl.actions.start('   ')
      expect(ctl.getState()).toBe(INITIAL_STATE)
      expect(f.api.createQuiz).not.toHaveBeenCalled()
    })
  })

  describe('polling', () => {
    it('streams questions in as the job runs', async () => {
      const f = makeFakes()
      f.api.createQuiz.mockResolvedValue({ job_id: 'j1' })
      f.api.getQuiz.mockResolvedValue(streamOf('j1', 'running', [aQuestion(0), aQuestion(1)]))
      const ctl = makeController(f)

      ctl.actions.start('Black holes')
      await flush()
      await flush()

      const s = ctl.getState()
      expect(s.phase).toBe('playing')
      expect(s.questions).toHaveLength(2)
      expect(s.optionOrder[0]).toBeDefined()
    })

    it('keeps polling until the quiz is finished', async () => {
      const f = makeFakes()
      f.api.createQuiz.mockResolvedValue({ job_id: 'j1' })
      let status = 'running'
      f.api.getQuiz.mockImplementation((jobId) =>
        Promise.resolve(streamOf(jobId, status, [aQuestion(0), aQuestion(1)])),
      )
      const ctl = makeController(f)

      ctl.actions.start('Black holes')
      await flush()
      await flush()
      const { optionOrder } = ctl.getState()
      ctl.actions.answer(0, optionOrder[0][0])
      ctl.actions.answer(1, optionOrder[1][0])
      expect(ctl.getState().phase).toBe('playing')

      status = 'completed'
      const callsBeforeFinish = f.api.getQuiz.mock.calls.length
      await vi.advanceTimersByTimeAsync(2000)
      expect(ctl.getState().phase).toBe('finished')
      expect(f.api.getQuiz.mock.calls.length).toBeGreaterThan(callsBeforeFinish)

      const callsAfterFinish = f.api.getQuiz.mock.calls.length
      await vi.advanceTimersByTimeAsync(2000)
      expect(f.api.getQuiz.mock.calls.length).toBe(callsAfterFinish)
    })

    it('surfaces a failed job and stops polling', async () => {
      const f = makeFakes()
      f.api.createQuiz.mockResolvedValue({ job_id: 'j1' })
      let status = 'running'
      f.api.getQuiz.mockImplementation((jobId) =>
        Promise.resolve(streamOf(jobId, status, [aQuestion(0)], status === 'failed' ? 'boom' : null)),
      )
      const ctl = makeController(f)

      ctl.actions.start('Black holes')
      await flush()
      await flush()
      expect(ctl.getState().phase).toBe('playing')

      status = 'failed'
      await vi.advanceTimersByTimeAsync(2000)
      expect(ctl.getState().phase).toBe('failed')
      expect(ctl.getState().error).toBe('boom')

      const calls = f.api.getQuiz.mock.calls.length
      await vi.advanceTimersByTimeAsync(2000)
      expect(f.api.getQuiz.mock.calls.length).toBe(calls)
    })

    it('retries transient poll failures on the next tick', async () => {
      const f = makeFakes()
      f.api.createQuiz.mockResolvedValue({ job_id: 'j1' })
      const ctl = makeController(f)

      ctl.actions.start('Black holes')
      await flush()

      f.api.getQuiz.mockRejectedValueOnce(new Error('flaky'))
      f.api.getQuiz.mockResolvedValue(streamOf('j1', 'running', [aQuestion(0)]))
      await vi.advanceTimersByTimeAsync(2000)
      expect(ctl.getState().phase).toBe('creating')

      await vi.advanceTimersByTimeAsync(2000)
      expect(ctl.getState().phase).toBe('playing')
    })
  })

  describe('restore', () => {
    it('resumes a stored session and starts polling again', async () => {
      const f = makeFakes()
      f.setUrlJob('j1')
      f.seed('j1', playingBlob('j1', [aQuestion(0)]))
      const ctl = makeController(f)

      const s = ctl.getState()
      expect(s.phase).toBe('playing')
      expect(s.topic).toBe('Black holes')

      await flush()
      expect(f.api.getQuiz).toHaveBeenCalledWith('j1')
    })

    it('reopens a session whose job is already finished', () => {
      const f = makeFakes()
      const blob = playingBlob('j1', [aQuestion(0)])
      blob.answers = { 0: blob.optionOrder[0][0] }
      blob.status = 'completed'
      blob.phase = 'finished'
      f.setUrlJob('j1')
      f.seed('j1', blob)
      const ctl = makeController(f)

      expect(ctl.getState().phase).toBe('finished')
    })

    it('falls back to a fresh session when nothing is stored for the job', () => {
      const f = makeFakes()
      f.setUrlJob('j1')
      const ctl = makeController(f)

      expect(ctl.getState().phase).toBe('creating')
      expect(ctl.getState().jobId).toBe('j1')
      expect(ctl.getState().topic).toBeNull()
    })

    it('does not pick up a blob stored under another job', () => {
      const f = makeFakes()
      f.setUrlJob('j1')
      f.seed('j1', { ...playingBlob('other', [aQuestion(0)]), jobId: 'other' })
      const ctl = makeController(f)

      expect(ctl.getState().phase).toBe('creating')
      expect(ctl.getState().jobId).toBe('j1')
      expect(ctl.getState().questions).toEqual([])
    })
  })

  describe('navigation', () => {
    it('records answers and moves through the set via actions', async () => {
      const f = makeFakes()
      f.api.createQuiz.mockResolvedValue({ job_id: 'j1' })
      f.api.getQuiz.mockResolvedValue(streamOf('j1', 'running', [aQuestion(0), aQuestion(1)]))
      const ctl = makeController(f)

      ctl.actions.start('Black holes')
      await flush()
      await flush()
      const { optionOrder } = ctl.getState()

      ctl.actions.answer(0, optionOrder[0][0])
      expect(ctl.getState().answers[0]).toBe(optionOrder[0][0])
      ctl.actions.next()
      expect(ctl.getState().currentIndex).toBe(1)
      ctl.actions.prev()
      expect(ctl.getState().currentIndex).toBe(0)
    })
  })

  describe('replay and new topic', () => {
    async function finishedController() {
      const f = makeFakes()
      f.api.createQuiz.mockResolvedValue({ job_id: 'j1' })
      f.api.getQuiz.mockImplementation((jobId) =>
        Promise.resolve(streamOf(jobId, 'completed', [aQuestion(0), aQuestion(1)])),
      )
      const ctl = makeController(f)
      ctl.actions.start('Black holes')
      await flush()
      await flush()
      const { optionOrder } = ctl.getState()
      ctl.actions.answer(0, optionOrder[0][0])
      ctl.actions.answer(1, optionOrder[1][0])
      expect(ctl.getState().phase).toBe('finished')
      return { f, ctl }
    }

    it('replay abandons the old session and creates a fresh one for the same topic', async () => {
      const { f, ctl } = await finishedController()

      f.api.createQuiz.mockResolvedValue({ job_id: 'j2' })
      ctl.actions.replay()
      expect(ctl.getState().phase).toBe('pending')
      expect(ctl.getState().topic).toBe('Black holes')
      expect(f.url.readJobId()).toBeNull()

      await flush()
      expect(ctl.getState().jobId).toBe('j2')
      expect(f.url.readJobId()).toBe('j2')
      expect(f.storage.loadSession('j1')).toBeNull()
    })

    it('new topic clears the session and returns to idle', async () => {
      const { f, ctl } = await finishedController()

      ctl.actions.newTopic()
      expect(ctl.getState()).toBe(INITIAL_STATE)
      expect(f.url.readJobId()).toBeNull()
      expect(f.storage.loadSession('j1')).toBeNull()
    })
  })

  describe('subscribe', () => {
    it('notifies listeners of every state change', async () => {
      const f = makeFakes()
      f.api.createQuiz.mockResolvedValue({ job_id: 'j1' })
      const ctl = makeController(f)
      const seen = []
      const unsubscribe = ctl.subscribe(() => seen.push(ctl.getState()))

      ctl.actions.start('Black holes')
      await flush()
      unsubscribe()

      expect(seen.map((s) => s.phase)).toEqual(['pending', 'creating'])
    })
  })
})