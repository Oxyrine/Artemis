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
  const headers = new Headers(init.headers)
  if (init.json !== undefined) headers.set('Content-Type', 'application/json')
  if (init.reviewer) headers.set('X-Reviewer-Id', init.reviewer)
  const res = await fetch(`/api${path}`, { ...init, headers, body: init.json !== undefined ? JSON.stringify(init.json) : init.body })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    const detail = typeof body.detail === 'string' ? body.detail : res.statusText || 'request failed'
    throw new ApiError(res.status, body.error ?? 'error', detail)
  }
  return res.json() as Promise<T>
}
