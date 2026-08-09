export function readJobId() {
  return new URLSearchParams(window.location.search).get('job')
}

export function writeJobId(jobId) {
  const params = new URLSearchParams(window.location.search)
  params.set('job', jobId)
  window.history.replaceState({}, '', `${window.location.pathname}?${params}`)
}

export function clearJobId() {
  const params = new URLSearchParams(window.location.search)
  params.delete('job')
  const qs = params.toString()
  window.history.replaceState({}, '', qs ? `${window.location.pathname}?${qs}` : window.location.pathname)
}
