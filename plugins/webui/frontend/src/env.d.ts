/// <reference types="vite/client" />

declare module '*.png' {
  const source: string
  export default source
}

declare module 'plantuml-encoder' {
  export function encode(source: string): string
  export function decode(source: string): string
}

declare module 'markdown-it-task-lists' {
  import type { PluginSimple } from 'markdown-it'
  const plugin: PluginSimple
  export default plugin
}
