import DOMPurify from 'dompurify'
import { slug } from 'github-slugger'
import hljs from 'highlight.js/lib/common'
import powershell from 'highlight.js/lib/languages/powershell'
import cmake from 'highlight.js/lib/languages/cmake'
import MarkdownIt from 'markdown-it'
import anchor from 'markdown-it-anchor'
import { full as emoji } from 'markdown-it-emoji'
import taskLists from 'markdown-it-task-lists'

hljs.registerLanguage('powershell', powershell)
hljs.registerLanguage('cmake', cmake)

const markdown = new MarkdownIt({ html: true, linkify: true })
  .use(anchor, { slugify: slug, tabIndex: false })
  .use(emoji)
  .use(taskLists)

markdown.core.ruler.push('project_toc', ({ tokens }) => {
  for (let index = 1; index < tokens.length - 1; index++) {
    const token = tokens[index]
    if (token.type !== 'inline' || !/^\[toc\]$/i.test(token.content.trim())
      || token.children?.length !== 1 || token.children[0].type !== 'text'
      || tokens[index - 1].type !== 'paragraph_open' || tokens[index - 1].level !== 0
      || tokens[index + 1].type !== 'paragraph_close') continue
    tokens[index - 1].hidden = true
    tokens[index + 1].hidden = true
    token.type = 'project_toc'
  }
})
markdown.renderer.rules.project_toc = () => '<nav class="markdown-toc" aria-label="目录" data-toc></nav>\n'

markdown.renderer.rules.fence = (tokens, index) => {
  const token = tokens[index]
  const language = token.info.trim().split(/\s+/)[0].toLowerCase()
  const escaped = markdown.utils.escapeHtml(token.content)
  if (['mermaid', 'plantuml', 'puml', 'uml'].includes(language)) {
    const type = language === 'mermaid' ? 'mermaid' : 'plantuml'
    return `<div class="markdown-diagram" data-diagram="${type}"><pre><code>${escaped}</code></pre></div>`
  }
  const code = language && hljs.getLanguage(language)
    ? hljs.highlight(token.content, { language, ignoreIllegals: true }).value
    : escaped
  return `<pre><code class="hljs language-${markdown.utils.escapeHtml(language)}">${code}</code></pre>`
}

export function renderMarkdown(source: string): DocumentFragment {
  const fragment = DOMPurify.sanitize(markdown.render(source), {
    USE_PROFILES: { html: true, svg: true, svgFilters: true },
    FORBID_TAGS: ['script', 'iframe', 'object', 'embed', 'form', 'button', 'textarea', 'select', 'foreignObject'],
    ADD_ATTR: ['data-diagram', 'data-toc'],
    ALLOW_DATA_ATTR: false,
    RETURN_DOM_FRAGMENT: true,
  })
  populateTableOfContents(fragment)
  return fragment
}

function populateTableOfContents(fragment: DocumentFragment): void {
  const markers = fragment.querySelectorAll('[data-toc]')
  if (!markers.length) return
  const list = document.createElement('ul')
  const parents: { level: number; item: HTMLLIElement }[] = []
  for (const heading of fragment.querySelectorAll<HTMLElement>('h1, h2, h3, h4, h5, h6')) {
    // Sanitization can remove IDs that collide with built-in DOM properties.
    if (!heading.id) {
      const base = `toc-${slug(heading.textContent || '')}`
      let id = base
      for (let suffix = 1; fragment.getElementById(id); suffix++) id = `${base}-${suffix}`
      heading.id = id
    }
    const level = Number(heading.tagName.slice(1))
    while (parents.length && parents.at(-1)!.level >= level) parents.pop()
    const parent = parents.at(-1)?.item
    let target = list
    if (parent) {
      target = parent.querySelector('ul') || document.createElement('ul')
      if (!target.parentNode) parent.append(target)
    }
    const item = document.createElement('li')
    const link = document.createElement('a')
    link.href = `#${encodeURIComponent(heading.id)}`
    link.textContent = heading.textContent
    item.append(link)
    target.append(item)
    parents.push({ level, item })
  }
  for (const marker of markers) {
    if (!list.children.length) marker.remove()
    else {
      marker.removeAttribute('data-toc')
      marker.append(list.cloneNode(true))
    }
  }
}

const PROJECT_ORIGIN = 'https://env-project.invalid'

export function resolveProjectUrl(value: string, sourcePath: string, image = false): string {
  const trimmed = value.trim()
  if (!trimmed || trimmed.startsWith('#')) return trimmed
  if (/^https?:\/\//i.test(trimmed)) return trimmed
  if (trimmed.startsWith('//')) return `https:${trimmed}`
  if (!image && /^mailto:/i.test(trimmed)) return trimmed
  if (image && /^data:image\//i.test(trimmed)) return trimmed
  if (/^[\w+.-]+:/.test(trimmed) || trimmed.includes('\\')) return ''
  try {
    const base = new URL(`/workspace/${sourcePath.split('/').map(encodeURIComponent).join('/')}`, PROJECT_ORIGIN)
    const url = new URL(trimmed.startsWith('/') ? `/workspace${trimmed}` : trimmed, base)
    if (!url.pathname.startsWith('/workspace/')) return ''
    const path = decodeURIComponent(url.pathname.slice('/workspace/'.length))
    if (path.split('/').some((part) => !part || part.startsWith('.') || /[:\\\x00]/.test(part))) return ''
    if (!image && path.toLowerCase().endsWith('.md')) {
      return `/?document=${encodeURIComponent(path)}${url.hash}`
    }
    return `/workspace-assets/${path.split('/').map(encodeURIComponent).join('/')}${url.search}${url.hash}`
  } catch {
    return ''
  }
}

export function prepareDocumentElements(root: ParentNode, sourcePath: string): void {
  for (const link of root.querySelectorAll('a')) {
    const href = link.getAttribute('href') || link.getAttribute('xlink:href') || ''
    const resolved = resolveProjectUrl(href, sourcePath)
    link.removeAttribute('xlink:href')
    if (resolved) link.setAttribute('href', resolved)
    else link.removeAttribute('href')
    if (resolved && !resolved.startsWith('#') && !resolved.startsWith('/?document=')) {
      link.setAttribute('target', '_blank')
      link.setAttribute('rel', 'noopener noreferrer')
    } else {
      link.removeAttribute('target')
    }
  }
  for (const image of root.querySelectorAll('img, image, use, feImage')) {
    const attribute = image.localName === 'img' ? 'src' : 'href'
    const src = image.getAttribute(attribute) || image.getAttribute('xlink:href') || ''
    image.removeAttribute('xlink:href')
    const resolved = resolveProjectUrl(src, sourcePath, true)
    if (resolved) image.setAttribute(attribute, resolved)
    else image.removeAttribute(attribute)
    if (image instanceof HTMLImageElement) {
      image.removeAttribute('srcset')
      image.setAttribute('referrerpolicy', 'no-referrer')
    }
  }
  for (const input of root.querySelectorAll('input')) {
    if (input.type === 'checkbox') input.disabled = true
    else input.remove()
  }
}

export function safeSvg(source: string): SVGSVGElement {
  const fragment = DOMPurify.sanitize(source, {
    USE_PROFILES: { svg: true, svgFilters: true },
    FORBID_TAGS: ['script', 'foreignObject'],
    ALLOW_DATA_ATTR: false,
    RETURN_DOM_FRAGMENT: true,
  })
  const svg = fragment.querySelector('svg')
  if (!svg) throw new Error('SVG 内容无效')
  return svg as SVGSVGElement
}
