let csrfToken = ''

export function setCsrfToken(value) {
  csrfToken = value
}

async function request(path, options = {}) {
  const method = options.method || 'GET'
  const headers = new Headers(options.headers || {})
  if (method !== 'GET') headers.set('X-Env-CSRF', csrfToken)
  if (options.json !== undefined) {
    headers.set('Content-Type', 'application/json')
    options.body = JSON.stringify(options.json)
  }
  const response = await fetch(path, {
    ...options,
    method,
    headers,
    credentials: 'same-origin',
  })
  const payload = await response.json().catch(() => ({}))
  if (!response.ok) {
    const error = new Error(payload.error?.message || `请求失败 (${response.status})`)
    error.code = payload.error?.code || 'request_failed'
    error.status = response.status
    error.details = payload.error?.details
    throw error
  }
  return payload.data
}

export const api = {
  session: () => request('/api/v1/session'),
  plugins: () => request('/api/v1/plugins'),
  plugin: (id) => request(`/api/v1/plugins/${encodeURIComponent(id)}`),
  doctor: (id) => request(`/api/v1/plugins/${encodeURIComponent(id)}/doctor`),
  uploadPackage: (file) => request('/api/v1/packages', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/vnd.rt-thread.epack',
      'X-Filename': encodeURIComponent(file.name),
    },
    body: file,
  }),
  installUpload: (uploadId, allowUnsigned) => request('/api/v1/plugins/install', {
    method: 'POST',
    json: { upload_id: uploadId, allow_unsigned: allowUnsigned },
  }),
  upgradeUpload: (pluginId, uploadId, allowUnsigned) => request(`/api/v1/plugins/${encodeURIComponent(pluginId)}/upgrade`, {
    method: 'POST',
    json: { upload_id: uploadId, allow_unsigned: allowUnsigned },
  }),
  setEnabled: (id, enabled) => request(`/api/v1/plugins/${encodeURIComponent(id)}/enabled`, {
    method: 'PUT',
    json: { enabled },
  }),
  setPermissions: (id, permissions) => request(`/api/v1/plugins/${encodeURIComponent(id)}/permissions`, {
    method: 'PUT',
    json: { permissions },
  }),
  uninstall: (id, purgeData) => request(`/api/v1/plugins/${encodeURIComponent(id)}?purge_data=${purgeData}`, {
    method: 'DELETE',
  }),
  marketStatus: () => request('/api/v1/market/status'),
  marketPlugins: (params = {}) => {
    const query = new URLSearchParams()
    if (params.q) query.set('q', params.q)
    if (params.sort) query.set('sort', params.sort)
    if (params.page) query.set('page', String(params.page))
    if (params.pageSize) query.set('page_size', String(params.pageSize))
    const suffix = query.toString()
    return request(`/api/v1/market/plugins${suffix ? `?${suffix}` : ''}`)
  },
  marketPlugin: (id) => request(`/api/v1/market/plugins/${encodeURIComponent(id)}`),
  prepareMarketPlugin: (id) => request(`/api/v1/market/plugins/${encodeURIComponent(id)}/prepare`, {
    method: 'POST',
    json: {},
  }),
}
