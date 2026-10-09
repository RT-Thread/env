export function isCloseWebUIShortcut(event: Pick<KeyboardEvent, 'key' | 'ctrlKey' | 'altKey' | 'metaKey' | 'shiftKey'>): boolean {
  return event.key.toLowerCase() === 'w'
    && event.ctrlKey
    && !event.altKey
    && !event.metaKey
    && !event.shiftKey
}
