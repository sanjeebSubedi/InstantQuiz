export function readJobId() {
  return new URLSearchParams(window.location.search).get('job')
}

export function writeJobId(jobId) {
  const params = new URLSearchParams(window.location.search)
  params.set('job', jobId)
  window.history.replaceState({}, '', `${window.location.pathname}?${params}`)
}