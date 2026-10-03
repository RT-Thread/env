<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { ArrowLeft } from '@element-plus/icons-vue'
import lightMarkdown from 'github-markdown-css/github-markdown-light.css?raw'
import darkMarkdown from 'github-markdown-css/github-markdown-dark.css?raw'
import lightCode from 'highlight.js/styles/github.css?raw'
import darkCode from 'highlight.js/styles/github-dark.css?raw'
import documentStyles from '../styles/markdown.css?raw'
import { api } from '../api'
import type { WorkspaceDocument } from '../types/api'
import { prepareDocumentElements, renderMarkdown, safeSvg } from '../utils/markdown'
import { plantUmlUrl, renderMermaid } from '../utils/diagrams'

const props = defineProps<{ homePath: string; theme: 'light' | 'dark' }>()
const documentData = ref<WorkspaceDocument | null>(null)
const loading = ref(false)
const error = ref('')
const contentHost = ref<HTMLElement>()
const requestedPath = ref(new URLSearchParams(window.location.search).get('document') || props.homePath)
const atHome = computed(() => requestedPath.value === props.homePath)
let loadGeneration = 0
let renderGeneration = 0
let svgAbort: AbortController | undefined

function scrollToHeading() {
  const root = contentHost.value?.shadowRoot
  if (!root || !window.location.hash) return
  try {
    const id = decodeURIComponent(window.location.hash.slice(1))
    root.getElementById(id)?.scrollIntoView({ block: 'start' })
  } catch { /* Ignore malformed URL fragments. */ }
}

async function loadDocument(resetScroll = false) {
  const generation = ++loadGeneration
  renderGeneration += 1
  svgAbort?.abort()
  loading.value = true
  error.value = ''
  try {
    const result = await api.workspaceDocument(requestedPath.value)
    if (generation !== loadGeneration) return
    documentData.value = result
    await nextTick()
    if (resetScroll && !window.location.hash) contentHost.value?.closest('.content-scroll')?.scrollTo({ top: 0 })
    await renderDocument()
  } catch (reason) {
    if (generation === loadGeneration) error.value = reason.message
  } finally {
    if (generation === loadGeneration) loading.value = false
  }
}

function navigate(path: string, hash = '', push = true) {
  if (push) {
    const url = new URL(window.location.href)
    if (path === props.homePath) url.searchParams.delete('document')
    else url.searchParams.set('document', path)
    url.hash = hash
    window.history.pushState({}, '', url)
  }
  if (requestedPath.value === path) scrollToHeading()
  else {
    requestedPath.value = path
    loadDocument(true)
  }
}

function onDocumentClick(event: MouseEvent) {
  if (event.defaultPrevented || event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return
  const link = event.composedPath().find((node) => node instanceof Element && node.localName === 'a') as Element | undefined
  const href = link?.getAttribute('href')
  if (!href) return
  if (href.startsWith('#')) {
    event.preventDefault()
    navigate(requestedPath.value, href)
  } else if (href.startsWith('/?document=')) {
    event.preventDefault()
    const url = new URL(href, window.location.origin)
    navigate(url.searchParams.get('document')!, url.hash)
  }
}

function showDiagramError(node: HTMLElement, message: string) {
  node.querySelector('pre')?.removeAttribute('hidden')
  const note = document.createElement('p')
  note.className = 'diagram-error'
  note.textContent = message
  node.append(note)
  node.setAttribute('aria-busy', 'false')
}

async function hydrateSvg(image: HTMLImageElement, signal: AbortSignal) {
  const url = new URL(image.src)
  if (url.origin !== window.location.origin || !url.pathname.startsWith('/workspace-assets/') || !url.pathname.toLowerCase().endsWith('.svg')) return
  try {
    const response = await fetch(url, { credentials: 'same-origin', signal })
    if (!response.ok) return
    const source = await response.text()
    if (signal.aborted) return
    const svg = safeSvg(source)
    const path = decodeURIComponent(url.pathname.slice('/workspace-assets/'.length))
    prepareDocumentElements(svg, path)
    const host = document.createElement('span')
    host.className = 'svg-image'
    host.setAttribute('role', svg.querySelector('a') ? 'group' : 'img')
    host.setAttribute('aria-label', image.alt || path)
    if (image.hasAttribute('width')) host.style.width = `${image.width}px`
    const shadow = host.attachShadow({ mode: 'open' })
    const style = document.createElement('style')
    style.textContent = ':host { max-width: 100%; } svg { display: block; max-width: 100%; height: auto; } a { cursor: pointer; }'
    shadow.append(style, svg)
    image.replaceWith(host)
  } catch (reason) {
    if (reason.name !== 'AbortError') image.title = reason.message
  }
}

async function renderDocument() {
  const host = contentHost.value
  const data = documentData.value
  if (!host || !data) return
  const generation = ++renderGeneration
  svgAbort?.abort()
  svgAbort = new AbortController()
  const signal = svgAbort.signal
  const root = host.shadowRoot || host.attachShadow({ mode: 'open' })
  const style = document.createElement('style')
  const dark = props.theme === 'dark'
  style.textContent = `${dark ? darkMarkdown : lightMarkdown}\n${dark ? darkCode : lightCode}\n${documentStyles}`
  const body = document.createElement('div')
  body.className = 'markdown-body'
  body.append(renderMarkdown(data.content))
  prepareDocumentElements(body, data.path)
  root.replaceChildren(style, body)
  scrollToHeading()
  const svgTasks = [...body.querySelectorAll('img')].map((image) => hydrateSvg(image, signal))
  const diagramTasks = [...body.querySelectorAll<HTMLElement>('[data-diagram]')].map(async (node) => {
    const source = node.querySelector('code')?.textContent || ''
    node.setAttribute('aria-busy', 'true')
    if (node.dataset.diagram === 'plantuml') {
      const image = document.createElement('img')
      image.alt = 'PlantUML 图'
      image.referrerPolicy = 'no-referrer'
      image.onload = () => {
        node.querySelector('pre')?.setAttribute('hidden', '')
        node.setAttribute('aria-busy', 'false')
      }
      image.onerror = () => {
        image.remove()
        showDiagramError(node, 'PlantUML 在线渲染未能加载')
      }
      image.src = plantUmlUrl(source, props.theme)
      node.append(image)
    } else {
      try {
        const svg = safeSvg(await renderMermaid(source, props.theme))
        if (generation !== renderGeneration) return
        node.querySelector('pre')?.setAttribute('hidden', '')
        node.append(svg)
        node.setAttribute('aria-busy', 'false')
      } catch (reason) {
        if (generation === renderGeneration) showDiagramError(node, `Mermaid 渲染失败：${reason.message}`)
      }
    }
  })
  await Promise.all([...svgTasks, ...diagramTasks])
  if (generation === renderGeneration) scrollToHeading()
}

function onHistoryChange() {
  navigate(new URLSearchParams(window.location.search).get('document') || props.homePath, window.location.hash, false)
}

watch(() => props.theme, () => renderDocument())
watch(() => props.homePath, (value, previous) => {
  if (requestedPath.value === previous) requestedPath.value = value
  loadDocument()
})
onMounted(() => {
  window.addEventListener('popstate', onHistoryChange)
  loadDocument()
})
onBeforeUnmount(() => {
  window.removeEventListener('popstate', onHistoryChange)
  loadGeneration += 1
  renderGeneration += 1
  svgAbort?.abort()
})
</script>

<template>
  <section class="project-document" :aria-busy="loading">
    <el-tooltip v-if="!atHome" content="返回项目文档首页">
      <el-button class="document-back" text circle :icon="ArrowLeft" aria-label="返回项目文档首页" @click="navigate(homePath)" />
    </el-tooltip>
    <el-alert v-if="error" :title="error" type="error" :closable="false" show-icon />
    <article v-show="!error" ref="contentHost" class="project-markdown" aria-label="项目文档" @click="onDocumentClick" />
  </section>
</template>
