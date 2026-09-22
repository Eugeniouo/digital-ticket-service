// Same-origin /api must be routed to the backend by the deployment proxy.
export class ApiError extends Error {
  constructor(status) {
    super(`API request failed (${status})`)
    this.status = status
  }
}

export async function request(path, { method = 'GET', body, signal } = {}) {
  const controller = new AbortController()
  const abort = () => controller.abort()
  signal?.addEventListener('abort', abort, { once: true })
  if (signal?.aborted) abort()
  const timeout = setTimeout(abort, 10000)
  try {
    const response = await fetch(`/api${path}`, {
      method,
      signal: controller.signal,
      cache: 'no-store',
      credentials: 'same-origin',
      headers: body ? { 'Content-Type': 'application/json' } : {},
      body: body ? JSON.stringify(body) : undefined,
    })
    if (!response.ok) throw new ApiError(response.status)
    return await response.json()
  } finally {
    clearTimeout(timeout)
    signal?.removeEventListener('abort', abort)
  }
}

const segment = encodeURIComponent
export const departmentPath = id => `/departments/${segment(id)}`
const ticketPath = ref => `${departmentPath(ref.departmentId)}/tickets/${segment(ref.ticketId)}`
export const ticketApi = {
  get: (ref, signal) => request(ticketPath(ref), { signal }),
  cancel: (ref, signal) => request(`${ticketPath(ref)}:cancel`, { method: 'POST', signal }),
  create: (departmentId, payload) => request(`${departmentPath(departmentId)}/tickets`, {
    method: 'POST', body: payload,
  }),
  statusHistory: (ref, signal) => request(`${ticketPath(ref)}/status-history`, { signal }),
}
