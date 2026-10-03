import { describe, expect, it } from 'vitest'
import { decode } from 'plantuml-encoder'
import { PLANTUML_SERVER, plantUmlUrl } from './diagrams'

describe('PlantUML rendering', () => {
  it('uses the online SVG renderer and follows the document theme', () => {
    const light = plantUmlUrl('Alice -> Bob: Hello', 'light')
    const dark = plantUmlUrl('@startuml\nAlice -> Bob: Hello\n@enduml', 'dark')
    expect(light).toMatch(/^https:\/\/www\.plantuml\.com\/plantuml\/svg\//)
    expect(decode(light.slice(PLANTUML_SERVER.length))).toContain('@startuml\n!theme plain\nAlice -> Bob: Hello\n@enduml')
    expect(decode(dark.slice(PLANTUML_SERVER.length))).toContain('!theme cyborg')
    expect(light).not.toBe(dark)
  })
})
