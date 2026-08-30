import { afterEach, describe, expect, it, vi } from 'vitest'
import { api, setCsrfToken } from './api'

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('local package API', () => {
  it('exposes SDK snapshot, plan, apply and task endpoints', async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ data: {} }) })
    vi.stubGlobal('fetch', fetchMock)
    setCsrfToken('csrf-token')

    await api.shutdown()
    await api.sdk()
    await api.sdkPlan([{ name: 'demo-gcc', enabled: true, version: 'v1' }])
    await api.sdkApply('plan-1', ['demo-gcc'])
    await api.sdkTask('task-1')
    await api.sdkCancelTask('task-1')
    await api.toolchains()
    await api.addToolchain({ name: 'gcc', path: '/opt/gcc', description: 'GCC' })
    await api.updateToolchain('gcc', { name: 'gcc-arm', path: '/opt/gcc-arm', description: 'ARM GCC' })
    await api.removeToolchain('gcc')
    await api.fileContextMenu()
    await api.installFileContextMenu()
    await api.removeFileContextMenu()

    expect(fetchMock.mock.calls.map(([path]) => path)).toEqual([
      '/api/v1/shutdown',
      '/api/v1/sdk',
      '/api/v1/sdk/plan',
      '/api/v1/sdk/apply',
      '/api/v1/sdk/tasks/task-1',
      '/api/v1/sdk/tasks/task-1/cancel',
      '/api/v1/settings/toolchains',
      '/api/v1/settings/toolchains',
      '/api/v1/settings/toolchains/gcc',
      '/api/v1/settings/toolchains/gcc',
      '/api/v1/settings/file-context-menu',
      '/api/v1/settings/file-context-menu/install',
      '/api/v1/settings/file-context-menu/remove',
    ])
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({})
    expect(JSON.parse(fetchMock.mock.calls[2][1].body)).toEqual({
      packages: [{ name: 'demo-gcc', enabled: true, version: 'v1' }],
    })
    expect(JSON.parse(fetchMock.mock.calls[3][1].body)).toEqual({
      plan_id: 'plan-1',
      confirm_remove: ['demo-gcc'],
    })
    expect(JSON.parse(fetchMock.mock.calls[5][1].body)).toEqual({})
  })

  it('installs only from an upload id', async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ data: {} }) })
    vi.stubGlobal('fetch', fetchMock)
    setCsrfToken('csrf-token')

    await api.installUpload('upload-1', true)

    const [path, options] = fetchMock.mock.calls[0]
    expect(path).toBe('/api/v1/plugins/install')
    expect(options.method).toBe('POST')
    expect(options.headers.get('X-Env-CSRF')).toBe('csrf-token')
    expect(JSON.parse(options.body)).toEqual({ upload_id: 'upload-1', allow_unsigned: true })
    const apiSurface = api as Record<string, unknown>
    expect(apiSurface.catalog).toBeUndefined()
    expect(apiSurface.installCatalog).toBeUndefined()
  })

  it('prepares an online plugin then still installs from an upload id', async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ data: { upload_id: 'upload-9' } }) })
    vi.stubGlobal('fetch', fetchMock)
    setCsrfToken('csrf-token')

    await api.prepareMarketPlugin('org.example.hello')
    await api.marketPlugins({ q: 'hello', sort: 'downloads' })

    expect(fetchMock.mock.calls[0][0]).toBe('/api/v1/market/plugins/org.example.hello/prepare')
    expect(fetchMock.mock.calls[0][1].method).toBe('POST')
    expect(fetchMock.mock.calls[1][0]).toBe('/api/v1/market/plugins?q=hello&sort=downloads')
  })

  it('upgrades only from an upload id', async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ data: {} }) })
    vi.stubGlobal('fetch', fetchMock)

    await api.upgradeUpload('org.example.plugin', 'upload-2', false)

    const [path, options] = fetchMock.mock.calls[0]
    expect(path).toBe('/api/v1/plugins/org.example.plugin/upgrade')
    expect(JSON.parse(options.body)).toEqual({ upload_id: 'upload-2', allow_unsigned: false })
  })

  it('keeps market error details for diagnosis', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 404,
      json: async () => ({
        error: {
          code: 'incompatible',
          message: 'no compatible artifact',
          details: { stage: 'resolve', diagnosis: { reason_code: 'incompatible' } },
        },
      }),
    })
    vi.stubGlobal('fetch', fetchMock)

    await expect(api.prepareMarketPlugin('org.example.hello')).rejects.toMatchObject({
      code: 'incompatible',
      details: { stage: 'resolve', diagnosis: { reason_code: 'incompatible' } },
    })
  })
})
