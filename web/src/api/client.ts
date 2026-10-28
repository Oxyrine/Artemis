/** The global audit list asks for the newest events only (the page shows newest first); one case's history is always complete. */
export const AUDIT_PAGE = 100

export class ApiError extends Error {
  status: number
  code: string
  constructor(status: number, code: string, message: string) {
    super(message)
    this.status = status
    this.code = code
  }
}

/** Every API error is {error, detail}; a policy refusal is a 409 whose detail is the reason to show the reviewer. */
export async function api<T>(path: string, init: RequestInit & { json?: unknown; reviewer?: string } = {}): Promise<T> {
  const timeout = new AbortController()
  const timer = setTimeout(() => timeout.abort(), 30_000)
  const headers = new Headers(init.headers)
  if (init.json !== undefined) headers.set('Content-Type', 'application/json')
  if (init.reviewer) headers.set('X-Reviewer-Id', init.reviewer)
  try {
    const res = await fetch(`/api${path}`, { ...init, headers,
      signal: init.signal ? AbortSignal.any([init.signal, timeout.signal]) : timeout.signal,
      body: init.json !== undefined ? JSON.stringify(init.json) : init.body })
    if (!res.ok) {
      const body = await res.json().catch(() => ({}))
      const fallback = res.status >= 500
        ? 'The investigation service is temporarily unavailable. Wait a moment, then retry.'
        : res.statusText || 'The request failed. Please try again.'
      throw new ApiError(res.status, body.error ?? 'error', typeof body.detail === 'string' ? body.detail : fallback)
    }
    return await res.json() as T
  } catch (error) {
    if (timeout.signal.aborted) throw new ApiError(0, 'timeout', 'The server did not respond in time. The action may still be running. Refresh to check its status before retrying.')
    if (error instanceof TypeError) throw new ApiError(0, 'network', 'Could not reach the investigation service. Check your connection and try again.')
    throw error
  } finally {
    clearTimeout(timer)
  }
}
