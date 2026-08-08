import { afterEach, describe, expect, it, vi } from 'vitest'
import { api, setCsrfToken } from './api.js'

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('local package API', () => {
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
    expect(api.catalog).toBeUndefined()
    expect(api.installCatalog).toBeUndefined()
  })

  it('upgrades only from an upload id', async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ data: {} }) })
    vi.stubGlobal('fetch', fetchMock)

    await api.upgradeUpload('org.example.plugin', 'upload-2', false)

    const [path, options] = fetchMock.mock.calls[0]
    expect(path).toBe('/api/v1/plugins/org.example.plugin/upgrade')
    expect(JSON.parse(options.body)).toEqual({ upload_id: 'upload-2', allow_unsigned: false })
  })
})
