import { describe, expect, it } from 'vitest'
import { hostBackendContext } from './plugins'

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
