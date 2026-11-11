const apiUrl = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '')

export async function api(path, options = {}) {
  let response
  try {
    response = await fetch(`${apiUrl}/api${path}`, {
      ...options,
      headers: { 'Content-Type': 'application/json', ...options.headers },
      body: options.body && typeof options.body !== 'string' ? JSON.stringify(options.body) : options.body,
    })
  } catch {
    throw new Error('Cannot reach LifePilot backend. Start FastAPI on port 8000.')
  }
  if (!response.ok) {
    let data = {}
    try { data = await response.json() } catch { /* no body */ }
    const detail = data.detail
    const message = Array.isArray(detail) ? detail.map(e => `${(e.loc || []).slice(1).join('.')}: ${e.msg}`).join('; ') : detail
    throw new Error(message || `Request failed (${response.status})`)
  }
  return response.json()
}

export const toIso = value => value ? new Date(value).toISOString() : null
export const toLocalInput = value => {
  if (!value) return ''
  const d = new Date(value)
  const pad = n => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}
export const todayLocal = () => {
  const d = new Date()
  const pad = n => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())}`
}
export const monthLocal = () => todayLocal().slice(0, 7)
export const rupees = value => '₹' + Number(value || 0).toLocaleString('en-IN', { maximumFractionDigits: 2, minimumFractionDigits: 0 })
export const niceDate = value => value ? new Date(value).toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' }) : 'No due date'
