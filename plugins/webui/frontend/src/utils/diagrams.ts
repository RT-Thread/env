import { encode } from 'plantuml-encoder'

export type DocumentTheme = 'light' | 'dark'
export const PLANTUML_SERVER = 'https://www.plantuml.com/plantuml/svg/'

export function plantUmlUrl(source: string, theme: DocumentTheme): string {
  const diagram = /^\s*@start\w+/i.test(source) ? source.trim() : `@startuml\n${source}\n@enduml`
  const themed = diagram.replace(/(^@start[^\n]*)(\n|$)/i, `$1\n!theme ${theme === 'dark' ? 'cyborg' : 'plain'}\n`)
  return PLANTUML_SERVER + encode(themed)
}

let renderQueue: Promise<unknown> = Promise.resolve()
let diagramId = 0

export function renderMermaid(source: string, theme: DocumentTheme): Promise<string> {
  // Mermaid owns global configuration; serialize initialization and rendering.
  const result = renderQueue.then(async () => {
    const { default: mermaid } = await import('mermaid')
    mermaid.initialize({
      startOnLoad: false,
      securityLevel: 'strict',
      theme: theme === 'dark' ? 'dark' : 'default',
      htmlLabels: false,
      flowchart: { htmlLabels: false },
      suppressErrorRendering: true,
    })
    const id = `env-mermaid-${++diagramId}`
    try {
      return (await mermaid.render(id, source)).svg
    } finally {
      document.getElementById(`d${id}`)?.remove()
    }
  })
  renderQueue = result.catch(() => {})
  return result
}
