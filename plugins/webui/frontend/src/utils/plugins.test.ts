import { describe, expect, it } from 'vitest'
import { iconMap } from '../constants'
import { hostBackendContext, iconFor } from './plugins'

describe('hostBackendContext', () => {
  it('returns browser-ready HTTP and WebSocket endpoints', () => {
    expect(hostBackendContext({
      base: '/plugin-assets/token/org.example.demo/',
      backend: {
        http_base: '/plugin-assets/token/org.example.demo/backend/',
        websocket_base: '/plugin-assets/token/org.example.demo/backend/',
      },
    }, 'http://127.0.0.1:49152/')).toEqual({
      httpBase: '/plugin-assets/token/org.example.demo/backend/',
      websocketBase: 'ws://127.0.0.1:49152/plugin-assets/token/org.example.demo/backend/',
    })
  })

  it('uses secure WebSocket transport for an HTTPS host', () => {
    expect(hostBackendContext({
      base: '/plugin-assets/token/org.example.demo/',
      backend: {
        http_base: '/backend/',
        websocket_base: '/backend/',
      },
    }, 'https://env.example/')).toMatchObject({
      websocketBase: 'wss://env.example/backend/',
    })
  })

  it('returns no backend for WebUI-only plugins', () => {
    expect(hostBackendContext({ base: '/plugin-assets/token/org.example.demo/', backend: null }, 'http://env/')).toBeNull()
  })
})

describe('plugin icons', () => {
  it('resolves the manifest icon through the shared icon helper', () => {
    const plugin = { webui: { entry: 'frontend/index.html', icon: 'shield-check' } }
    expect(iconFor(plugin)).toBe(iconMap['shield-check'])
    expect(iconFor(plugin)).toBe(iconFor(plugin))
  })

  it('uses the same fallback for plugins without a known icon', () => {
    const plugin = { webui: { entry: 'frontend/index.html', icon: 'unknown-icon' } }
    expect(iconFor(plugin)).toBe(iconFor({ webui: { entry: 'frontend/index.html', icon: 'puzzle' } }))
  })

  it('falls back to the default component until an image asset URL is available', () => {
    expect(iconFor({
      webui: { entry: 'frontend/index.html', icon: { type: 'svg', path: 'frontend/icon.svg' } },
    })).toBe(iconFor({}))
  })
})
