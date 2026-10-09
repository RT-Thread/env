import { describe, expect, it } from 'vitest'
import { isCloseWebUIShortcut } from './shortcuts'

describe('WebUI shortcuts', () => {
  it('matches Ctrl+W without modifier combinations', () => {
    expect(isCloseWebUIShortcut({ key: 'w', ctrlKey: true, altKey: false, metaKey: false, shiftKey: false })).toBe(true)
    expect(isCloseWebUIShortcut({ key: 'W', ctrlKey: true, altKey: false, metaKey: false, shiftKey: false })).toBe(true)
    expect(isCloseWebUIShortcut({ key: 'w', ctrlKey: false, altKey: false, metaKey: false, shiftKey: false })).toBe(false)
    expect(isCloseWebUIShortcut({ key: 'w', ctrlKey: true, altKey: false, metaKey: false, shiftKey: true })).toBe(false)
  })
})
