import type {
  ContextMenuSnapshot,
  DoctorResult,
  EnvPlugin,
  MarketCatalog,
  MarketStatus,
  SdkPlan,
  SdkRequestPackage,
  SdkSnapshot,
  SdkTask,
  Session,
  ToolchainEntry,
  ToolchainSnapshot,
  UploadSummary,
} from './types/api'
import { ApiError } from './types/api'

type JsonValue = Record<string, unknown> | unknown[] | string | number | boolean | null
type ApiRequestOptions = Omit<RequestInit, 'body'> & { body?: BodyInit | null; json?: JsonValue }

let csrfToken = ''

export function setCsrfToken(value: string): void {
  csrfToken = value
}

async function request<T>(path: string, options: ApiRequestOptions = {}): Promise<T> {
  const method = options.method || 'GET'
  const headers = new Headers(options.headers || {})
  if (method !== 'GET') headers.set('X-Env-CSRF', csrfToken)

  const requestInit: RequestInit = { ...options, method, headers }
  delete (requestInit as ApiRequestOptions).json
  if (options.json !== undefined) {
    headers.set('Content-Type', 'application/json')
    requestInit.body = JSON.stringify(options.json)
  }

  const response = await fetch(path, {
    ...requestInit,
    method,
    headers,
    credentials: 'same-origin',
  })
  const payload = await response.json().catch(() => ({})) as {
    data?: T
    error?: { code?: string; message?: string; details?: Record<string, unknown> }
  }
  if (!response.ok) {
    throw new ApiError(
      payload.error?.message || `请求失败 (${response.status})`,
      payload.error?.code || 'request_failed',
      response.status,
      payload.error?.details,
    )
  }
  return payload.data as T
}

export const api = {
  session: (): Promise<Session> => request('/api/v1/session'),
  shutdown: (): Promise<Record<string, unknown>> => request('/api/v1/shutdown', { method: 'POST', json: {} }),
  plugins: (): Promise<EnvPlugin[]> => request('/api/v1/plugins'),
  sdk: (): Promise<SdkSnapshot> => request('/api/v1/sdk'),
  sdkPlan: (packages: SdkRequestPackage[]): Promise<SdkPlan> => request('/api/v1/sdk/plan', { method: 'POST', json: { packages } }),
  sdkApply: (planId: string, confirmRemove: string[] = []): Promise<SdkTask> => request('/api/v1/sdk/apply', { method: 'POST', json: { plan_id: planId, confirm_remove: confirmRemove } }),
  sdkTask: (taskId: string): Promise<SdkTask> => request(`/api/v1/sdk/tasks/${encodeURIComponent(taskId)}`),
  sdkCancelTask: (taskId: string): Promise<SdkTask> => request(`/api/v1/sdk/tasks/${encodeURIComponent(taskId)}/cancel`, { method: 'POST', json: {} }),
  toolchains: (): Promise<ToolchainSnapshot> => request('/api/v1/settings/toolchains'),
  addToolchain: (entry: ToolchainEntry): Promise<ToolchainSnapshot> => request('/api/v1/settings/toolchains', { method: 'POST', json: entry }),
  updateToolchain: (name: string, entry: ToolchainEntry): Promise<ToolchainSnapshot> => request(`/api/v1/settings/toolchains/${encodeURIComponent(name)}`, { method: 'PUT', json: entry }),
  removeToolchain: (name: string): Promise<ToolchainSnapshot> => request(`/api/v1/settings/toolchains/${encodeURIComponent(name)}`, { method: 'DELETE' }),
  fileContextMenu: (): Promise<ContextMenuSnapshot> => request('/api/v1/settings/file-context-menu'),
  installFileContextMenu: (): Promise<ContextMenuSnapshot> => request('/api/v1/settings/file-context-menu/install', { method: 'POST', json: {} }),
  removeFileContextMenu: (): Promise<ContextMenuSnapshot> => request('/api/v1/settings/file-context-menu/remove', { method: 'POST', json: {} }),
  plugin: (id: string): Promise<EnvPlugin> => request(`/api/v1/plugins/${encodeURIComponent(id)}`),
  doctor: (id: string): Promise<DoctorResult> => request(`/api/v1/plugins/${encodeURIComponent(id)}/doctor`),
  uploadPackage: (file: File): Promise<UploadSummary> => request('/api/v1/packages', {
    method: 'POST',
    headers: { 'Content-Type': 'application/vnd.rt-thread.epack', 'X-Filename': encodeURIComponent(file.name) },
    body: file,
  }),
  installUpload: (uploadId: string, allowUnsigned: boolean): Promise<EnvPlugin> => request('/api/v1/plugins/install', { method: 'POST', json: { upload_id: uploadId, allow_unsigned: allowUnsigned } }),
  upgradeUpload: (pluginId: string, uploadId: string, allowUnsigned: boolean): Promise<EnvPlugin> => request(`/api/v1/plugins/${encodeURIComponent(pluginId)}/upgrade`, { method: 'POST', json: { upload_id: uploadId, allow_unsigned: allowUnsigned } }),
  setEnabled: (id: string, enabled: boolean): Promise<EnvPlugin> => request(`/api/v1/plugins/${encodeURIComponent(id)}/enabled`, { method: 'PUT', json: { enabled } }),
  setPermissions: (id: string, permissions: string[]): Promise<EnvPlugin> => request(`/api/v1/plugins/${encodeURIComponent(id)}/permissions`, { method: 'PUT', json: { permissions } }),
  uninstall: (id: string, purgeData: boolean): Promise<Record<string, unknown>> => request(`/api/v1/plugins/${encodeURIComponent(id)}?purge_data=${purgeData}`, { method: 'DELETE' }),
  marketStatus: (): Promise<MarketStatus> => request('/api/v1/market/status'),
  marketPlugins: (params: { q?: string; sort?: string; page?: number; pageSize?: number } = {}): Promise<MarketCatalog> => {
    const query = new URLSearchParams()
    if (params.q) query.set('q', params.q)
    if (params.sort) query.set('sort', params.sort)
    if (params.page) query.set('page', String(params.page))
    if (params.pageSize) query.set('page_size', String(params.pageSize))
    const suffix = query.toString()
    return request(`/api/v1/market/plugins${suffix ? `?${suffix}` : ''}`)
  },
  marketPlugin: (id: string): Promise<EnvPlugin> => request(`/api/v1/market/plugins/${encodeURIComponent(id)}`),
  prepareMarketPlugin: (id: string): Promise<UploadSummary> => request(`/api/v1/market/plugins/${encodeURIComponent(id)}/prepare`, { method: 'POST', json: {} }),
}
