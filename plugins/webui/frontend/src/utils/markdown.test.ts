// @vitest-environment jsdom
import { describe, expect, it } from 'vitest'
import { prepareDocumentElements, renderMarkdown, resolveProjectUrl, safeSvg } from './markdown'

describe('project Markdown', () => {
  it('renders headings, GitHub tables, task lists, emoji and highlighted code', () => {
    const result = renderMarkdown('# Project\n\n## Guide\n\n| Name | State |\n| --- | --- |\n| Env | Ready |\n\n- [x] Done\n\n:rocket:\n\n```python\nprint("hello")\n```')
    expect(result.querySelector('h1')?.id).toBe('project')
    expect(result.querySelector('h2')?.id).toBe('guide')
    expect(result.querySelector('table td')?.textContent).toBe('Env')
    expect(result.querySelector<HTMLInputElement>('input')?.checked).toBe(true)
    expect(result.textContent).toContain('\u{1f680}')
    expect(result.querySelector('pre code .hljs-string')).not.toBeNull()
  })

  it('expands standalone TOC markers into nested links using the rendered heading IDs', () => {
    const result = renderMarkdown('[toc]\n\n# Project\n\n## Guide\n\n### Details\n\n## Guide\n\n### 使用 `Env` :rocket:\n\n[TOC]')
    const directories = result.querySelectorAll('nav.markdown-toc')
    expect(directories).toHaveLength(2)
    const headings = [...result.querySelectorAll<HTMLElement>('h1, h2, h3')]
    const links = [...directories[0].querySelectorAll('a')]
    expect(links.map((link) => link.getAttribute('href'))).toEqual(headings.map((heading) => `#${encodeURIComponent(heading.id)}`))
    expect(links.map((link) => link.textContent)).toEqual(headings.map((heading) => heading.textContent))
    expect(headings[3].id).toBe('guide-1')
    expect(directories[0].querySelectorAll(':scope > ul > li')).toHaveLength(1)
    expect(directories[0].querySelectorAll(':scope > ul > li > ul > li')).toHaveLength(2)
    expect(directories[0].innerHTML).toBe(directories[1].innerHTML)
    expect(result.querySelector('[data-toc]')).toBeNull()
    prepareDocumentElements(result, 'index.md')
    expect(links.every((link) => !link.hasAttribute('target'))).toBe(true)
    expect(renderMarkdown('[toc]\n\n## Guide').querySelector('nav a')?.getAttribute('href')).toBe('#guide')
  })

  it('handles missing and skipped heading levels without empty directory entries', () => {
    expect(renderMarkdown('Before\n\n[toc]\n\nAfter').querySelector('nav')).toBeNull()
    expect(renderMarkdown('# No marker').querySelector('nav')).toBeNull()
    const result = renderMarkdown('  [ToC]  \n\n### Start\n\n##### Deep\n\n###### Deeper\n\n## Next')
    const directory = result.querySelector('nav')!
    expect(directory.querySelectorAll(':scope > ul > li > a')).toHaveLength(2)
    expect(directory.querySelectorAll('li')).toHaveLength(4)
    expect(directory.querySelector('li li li a')?.textContent).toBe('Deeper')
    expect([...directory.querySelectorAll('li')].every((item) => item.firstElementChild?.tagName === 'A')).toBe(true)
  })

  it('keeps literal TOC text in code, escaped text, links and regular paragraphs', () => {
    const source = '# [toc]\n\n`[toc]`\n\n```markdown\n[toc]\n```\n\n\\[toc]\n\nPrefix [toc]\n\n[toc] suffix\n\n- [toc]\n\n> [toc]\n\n[toc](https://example.com)'
    const result = renderMarkdown(source)
    expect(result.querySelector('nav')).toBeNull()
    expect(result.querySelector('pre code')?.textContent).toBe('[toc]\n')
    expect(result.querySelector('p code')?.textContent).toBe('[toc]')
    expect(renderMarkdown('[toc]\n\n[toc]: https://example.com').querySelector('nav')).toBeNull()
  })

  it('uses safe plain heading labels in the directory', () => {
    const result = renderMarkdown('[toc]\n\n## **Build** [guide](https://example.com)\n\n## <img src="x" onerror="alert(1)">Title')
    const directory = result.querySelector('nav')!
    expect(directory.querySelector('a')?.textContent).toBe('Build guide')
    expect(directory.querySelectorAll('a')).toHaveLength(2)
    expect(directory.querySelector('img, strong, script, [onerror], a a')).toBeNull()
  })

  it('assigns unique safe anchors when sanitization removes DOM-property IDs', () => {
    const result = renderMarkdown('[toc]\n\n# Title\n\n## Images\n\n## Title\n\n## toc-title')
    const headings = [...result.querySelectorAll<HTMLElement>('h1, h2')]
    expect(headings.map((heading) => heading.id)).toEqual(['toc-title-1', 'toc-images', 'title-1', 'toc-title'])
    expect([...result.querySelectorAll('nav a')].map((link) => link.getAttribute('href'))).toEqual(headings.map((heading) => `#${heading.id}`))
    expect(result.querySelector('nav a')?.textContent).toBe('Title')
  })

  it('preserves expanded HTML tables but removes executable content', () => {
    const result = renderMarkdown('<table><tr><th colspan="2">Title</th></tr><tr><td rowspan="2">A</td><td>B</td></tr></table>\n\n<script>alert(1)</script><iframe src="/api/v1/session"></iframe><img src="x.png" onerror="alert(1)"><a href="javascript:alert(1)">unsafe</a>')
    expect(result.querySelector('th')?.getAttribute('colspan')).toBe('2')
    expect(result.querySelector('td')?.getAttribute('rowspan')).toBe('2')
    expect(result.querySelector('script, iframe, [onerror]')).toBeNull()
    expect(result.querySelector('a')?.getAttribute('href')).toBeNull()
  })

  it('highlights the PowerShell code used by Env project documentation', () => {
    const result = renderMarkdown('```powershell\nWrite-Host "Hello Env"\n```')
    expect(result.querySelector('.hljs-built_in')).not.toBeNull()
    expect(result.querySelector('.hljs-string')?.textContent).toBe('"Hello Env"')
  })

  it('retains diagram source for Mermaid and online PlantUML hydration', () => {
    const result = renderMarkdown('```mermaid\ngraph LR\nA --> B\n```\n\n```puml\nAlice -> Bob\n```')
    expect(result.querySelectorAll('[data-diagram]')).toHaveLength(2)
    expect(result.querySelector('[data-diagram="plantuml"] code')?.textContent).toContain('Alice -> Bob')
  })

  it('resolves project images, document navigation and nested SVG links', () => {
    expect(resolveProjectUrl('../images/a b.svg', 'docs/guide.md', true)).toBe('/workspace-assets/images/a%20b.svg')
    expect(resolveProjectUrl('/images/a.png', 'docs/guide.md', true)).toBe('/workspace-assets/images/a.png')
    expect(resolveProjectUrl('../README.md#guide', 'images/map.svg')).toBe('/?document=README.md#guide')
    expect(resolveProjectUrl('#guide', 'index.md')).toBe('#guide')
    expect(resolveProjectUrl('https://example.com/a.svg', 'index.md', true)).toBe('https://example.com/a.svg')
    expect(resolveProjectUrl('../../private.svg', 'index.md', true)).toBe('')
    expect(resolveProjectUrl('.hidden/notes.md', 'index.md')).toBe('')
    expect(resolveProjectUrl('javascript:alert(1)', 'index.md')).toBe('')
  })

  it('sanitizes SVG while preserving clickable links and local image references', () => {
    const svg = safeSvg('<svg xmlns="http://www.w3.org/2000/svg"><style>text { fill: red }</style><a href="../docs/guide.md#guide"><text>Guide</text></a><image href="a.png"/><script>alert(1)</script><foreignObject><div>unsafe</div></foreignObject></svg>')
    prepareDocumentElements(svg, 'images/map.svg')
    expect(svg.querySelector('script, foreignObject')).toBeNull()
    expect(svg.querySelector('style')).not.toBeNull()
    expect(svg.querySelector('a')?.getAttribute('href')).toBe('/?document=docs%2Fguide.md#guide')
    expect(svg.querySelector('image')?.getAttribute('href')).toBe('/workspace-assets/images/a.png')
  })
})
