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
