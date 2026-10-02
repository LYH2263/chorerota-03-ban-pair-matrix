export async function api(path, opts = {}) {
  const r = await fetch('/api' + path, {
    headers: { 'Content-Type': 'application/json', ...(opts.headers || {}) },
    ...opts,
  })
  if (!r.ok) {
    let detail = r.statusText
    let body = null
    try { body = await r.json(); detail = body.detail || JSON.stringify(body) } catch {}
    const msg = typeof detail === 'string' ? detail : (detail.reason || JSON.stringify(detail))
    const err = new Error(msg)
    err.status = r.status
    err.detail = typeof detail === 'object' ? detail : null  // 结构化回包（如 unassignable_slot）
    err.body = body
    throw err
  }
  if (r.status === 204) return null
  return r.json()
}
