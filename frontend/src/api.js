export async function api(path, opts = {}) {
  const r = await fetch('/api' + path, {
    headers: { 'Content-Type': 'application/json', ...(opts.headers || {}) },
    ...opts,
  })
  if (!r.ok) {
    let detail = r.statusText
    try { const j = await r.json(); detail = j.detail || JSON.stringify(j) } catch {}
    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail))
  }
  if (r.status === 204) return null
  return r.json()
}

const REASONS = {
  duplicate_exclusion: '禁配已存在，矩阵未增行',
  member_not_found: '成员不存在',
  task_not_found: '任务不存在',
  member_not_assignable: '成员已停用或数据脏，不可设禁配',
  exclusion_not_found: '禁配不存在',
  exclusion_conflict: '对调会形成禁配对，已拒绝，格表未动',
  slot_missing: '格位不存在',
  same_assignee: '两格同属一人',
  same_slot: '同一格位',
  not_pending: '对调单不在待确认状态',
}
export function reasonText(code) { return REASONS[code] || code }
