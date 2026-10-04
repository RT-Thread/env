import { expect, test } from '@playwright/test'
import { spawn } from 'node:child_process'
import { cp, mkdir, mkdtemp, rm, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { resolve } from 'node:path'

let serverProcess: ReturnType<typeof spawn>
let root: string
let origin: string
let cookies

const plantUmlSvg = '<svg xmlns="http://www.w3.org/2000/svg" width="300" height="110"><rect width="300" height="110" fill="#e1f1ee"/><text x="20" y="60" fill="#17201c">PlantUML sequence</text></svg>'

test.beforeAll(async ({ browser, request }) => {
  root = await mkdtemp(resolve(tmpdir(), 'env-project-document-'))
  const repository = resolve(process.cwd(), '../../..')
  await mkdir(resolve(root, 'images'))
  await mkdir(resolve(root, 'docs'))
  await cp(resolve(repository, 'assets/env.png'), resolve(root, 'images/env.png'))
  const imagePage = await browser.newPage()
  const jpeg = await imagePage.evaluate(() => {
    const canvas = document.createElement('canvas')
    canvas.width = 300
    canvas.height = 80
    const ctx = canvas.getContext('2d')!
    ctx.fillStyle = '#e1f1ee'
    ctx.fillRect(0, 0, 300, 80)
    ctx.fillStyle = '#17201c'
    ctx.font = '20px sans-serif'
    ctx.fillText('Project image - JPEG', 20, 46)
    return canvas.toDataURL('image/jpeg').split(',')[1]
  })
  await imagePage.close()
  await writeFile(resolve(root, 'images/project.jpeg'), Buffer.from(jpeg, 'base64'))
  await writeFile(resolve(root, 'README.md'), '# README fallback\n\n[Home](index.md)\n')
  await writeFile(resolve(root, 'docs/guide.md'), '# Project guide\n\n## Details\n\n[Back home](../index.md)\n\n![Nested image](../images/env.png)\n')
  await writeFile(resolve(root, 'images/map.svg'), `<svg xmlns="http://www.w3.org/2000/svg" width="600" height="100" viewBox="0 0 600 100">
<style>.nav-entry { display: none } text { fill: currentColor; font: 18px sans-serif }</style>
<rect x="1" y="1" width="598" height="98" rx="4" fill="#e1f1ee" stroke="#0f766e"/>
<a href="../docs/guide.md#details"><text x="24" y="56" style="fill:#17201c">Open guide</text></a>
<a href="https://example.com"><text x="300" y="56" style="fill:#17201c">External link</text></a>
<script>window.__svgExecuted = true</script></svg>`)
  await writeFile(resolve(root, 'index.md'), `# Env Project :rocket:

[toc]

[Features](#features) · [Guide](docs/guide.md#details)

## Features

| Format | Status |
| --- | --- |
| Markdown | **Ready** |
| SVG links | Ready |

- [x] Project homepage
- [ ] Release

### Code

\`\`\`python
def build_project():
    print("Hello Env")
\`\`\`

### Expanded table

<table><tr><th colspan="2">Merged header</th></tr><tr><td rowspan="2">Platform</td><td>Linux</td></tr><tr><td>Windows</td></tr></table>

## Images

![Env logo](images/env.png)

![Project JPEG](images/project.jpeg)

![Clickable SVG](images/map.svg)

## Diagrams

\`\`\`mermaid
flowchart LR
    Source --> Build --> Ready
\`\`\`

\`\`\`plantuml
@startuml
Alice -> Bob: Build project
Bob --> Alice: Ready
@enduml
\`\`\`

#### Heading four
##### Heading five
###### Heading six

<script>window.__markdownExecuted = true</script>
<a href="javascript:alert(1)">Unsafe link</a>
`)
  await writeFile(resolve(root, 'rtconfig.py'), '# Test workspace\n')
  await writeFile(resolve(root, 'SConstruct'), `import struct
import time
def link(target, source, env):
    print('Build log: compiling project')
    time.sleep(1.5)
    with open(str(target[0]), 'wb') as output:
        output.write(b'\\x7fELF' + b'\\x02\\x01' + b'\\x00' * 10 + struct.pack('<H', 2))
    print('Build log: firmware ready')
    return 0
Default(Command('firmware.elf', [], link))
`)
  serverProcess = spawn('python', [
    resolve(repository, 'env.py'), 'webui', '--no-browser', '--port', '0', '--env-root', resolve(root, 'env'),
  ], { cwd: root, env: { ...process.env, PYTHONUNBUFFERED: '1', ENV_PLUGIN_MARKET_URL: '' }, stdio: ['ignore', 'pipe', 'pipe'] })
  const launchUrl = await new Promise<string>((resolveUrl, reject) => {
    let output = ''
    const timer = setTimeout(() => reject(new Error(`WebUI startup timed out: ${output}`)), 10_000)
    serverProcess.stdout!.on('data', (chunk) => {
      output += chunk.toString()
      const match = output.match(/Launch URL: (http:\/\/[^\s]+)/)
      if (match) { clearTimeout(timer); resolveUrl(match[1]) }
    })
    serverProcess.stderr!.on('data', (chunk) => { output += chunk.toString() })
    serverProcess.on('exit', (code) => { clearTimeout(timer); reject(new Error(`WebUI exited ${code}: ${output}`)) })
  })
  origin = new URL(launchUrl).origin
  await request.get(launchUrl)
  cookies = (await request.storageState()).cookies
})

test.afterAll(async () => {
  if (serverProcess && serverProcess.exitCode === null) {
    serverProcess.kill('SIGINT')
    await new Promise((done) => serverProcess.once('exit', done))
  }
  if (root && process.env.ENV_WEBUI_KEEP_PREVIEW !== '1') await rm(root, { recursive: true, force: true })
  else if (root) {
    await rm(resolve(root, 'firmware.elf'), { force: true })
    console.log(`Project document preview workspace: ${root}`)
  }
})

test.beforeEach(async ({ context, page }) => {
  await context.addCookies(cookies)
  // Keep automated tests deterministic; online rendering is checked separately.
  await page.route('https://www.plantuml.com/plantuml/svg/**', (route) => route.fulfill({
    contentType: 'image/svg+xml', headers: { 'Cache-Control': 'no-store' }, body: plantUmlSvg,
  }))
  await page.goto(origin)
  await expect(page.locator('.project-markdown h1')).toContainText('Env Project')
})

test('renders GitHub Markdown, HTML tables, images and diagrams on desktop', async ({ page }, info) => {
  const errors: string[] = []
  page.on('pageerror', (error) => errors.push(error.message))
  await page.setViewportSize({ width: 1440, height: 1000 })
  const doc = page.locator('.project-markdown')
  await expect(page.locator('.document-toolbar, .document-location')).toHaveCount(0)
  await expect(page.getByRole('button', { name: '刷新项目文档' })).toHaveCount(0)
  await expect(page.getByRole('button', { name: '返回项目文档首页' })).toHaveCount(0)
  await expect(page.locator('.home-result')).toHaveCount(0)
  await expect(doc.locator('table')).toHaveCount(2)
  await expect(doc.locator('th[colspan="2"]')).toHaveText('Merged header')
  await expect(doc.locator('td[rowspan="2"]')).toHaveText('Platform')
  await expect(doc.locator('input:checked')).toHaveCount(1)
  await expect(doc.locator('.hljs-keyword')).toContainText('def')
  await expect(doc.locator('h1')).toContainText('\u{1f680}')
  await expect(doc.locator('.svg-image svg')).toBeVisible()
  await expect(doc.locator('[data-diagram="mermaid"] > svg')).toBeVisible()
  await expect(doc.locator('[data-diagram="plantuml"] > img')).toBeVisible()
  expect(await doc.locator('img[src$=".png"], img[src$=".jpeg"]').evaluateAll((images: HTMLImageElement[]) => images.every((image) => image.complete && image.naturalWidth > 0))).toBe(true)
  expect(await page.evaluate(() => window['__markdownExecuted'] || window['__svgExecuted'])).toBeUndefined()
  await expect(page.locator('.nav-entry').filter({ hasText: '项目首页' })).toBeVisible()
  await doc.locator('h1').scrollIntoViewIfNeeded()
  await page.screenshot({ path: info.outputPath('desktop-light.png') })
  await doc.locator('#diagrams').scrollIntoViewIfNeeded()
  await page.screenshot({ path: info.outputPath('desktop-diagrams.png') })
  expect(errors).toEqual([])
})

test('table of contents follows heading levels and links to the document anchors', async ({ page }) => {
  const doc = page.locator('.project-markdown')
  const directory = doc.getByRole('navigation', { name: '目录' })
  await expect(directory).toBeVisible()
  await expect(directory.locator('a')).toHaveCount(9)
  await expect(directory.locator(':scope > ul > li')).toHaveCount(1)
  await expect(directory.locator(':scope > ul > li > ul > li')).toHaveCount(3)
  await directory.getByRole('link', { name: 'Heading six', exact: true }).click()
  await expect(page).toHaveURL(/#heading-six$/)
  await expect(doc.locator('#heading-six')).toBeInViewport()
  await page.reload()
  await expect(doc.locator('#heading-six')).toBeInViewport()
  await page.getByRole('button', { name: '设置', exact: true }).click()
  await page.getByText('深色', { exact: true }).click()
  await page.getByRole('button', { name: '项目首页', exact: true }).click()
  await directory.getByRole('link', { name: 'Features', exact: true }).click()
  await expect(page).toHaveURL(/#features$/)
  await expect(doc.locator('#features')).toBeInViewport()
})

test('SVG links navigate within the workspace and browser history restores the home', async ({ page }) => {
  const svgLink = page.locator('.svg-image a').filter({ hasText: 'Open guide' })
  await expect(svgLink).toHaveAttribute('href', '/?document=docs%2Fguide.md#details')
  await svgLink.focus()
  await page.keyboard.press('Enter')
  await expect(page.locator('.project-markdown h1')).toHaveText('Project guide')
  await expect(page).toHaveURL(/document=docs%2Fguide\.md#details/)
  await expect(page.locator('.project-markdown #details')).toBeInViewport()
  await page.goBack()
  await expect(page.locator('.project-markdown h1')).toContainText('Env Project')
  await page.locator('.project-markdown a').filter({ hasText: /^Guide$/ }).click()
  await expect(page.locator('.project-markdown h1')).toHaveText('Project guide')
  await page.getByRole('button', { name: '返回项目文档首页' }).click()
  await expect(page.locator('.project-markdown h1')).toContainText('Env Project')
})

test('dark theme updates code highlighting and diagrams', async ({ page }, info) => {
  const code = page.locator('.project-markdown .hljs-keyword').first()
  const lightCodeColor = await code.evaluate((node) => getComputedStyle(node).color)
  const lightPlantUml = await page.locator('[data-diagram="plantuml"] > img').getAttribute('src')
  await page.getByRole('button', { name: '设置', exact: true }).click()
  await page.getByText('深色', { exact: true }).click()
  await page.getByRole('button', { name: '项目首页', exact: true }).click()
  await expect(page.locator('.project-markdown h1')).toContainText('Env Project')
  expect(await code.evaluate((node) => getComputedStyle(node).color)).not.toBe(lightCodeColor)
  await expect(page.locator('[data-diagram="mermaid"] > svg')).toBeVisible()
  expect(await page.locator('[data-diagram="plantuml"] > img').getAttribute('src')).not.toBe(lightPlantUml)
  await page.locator('.project-markdown h1').scrollIntoViewIfNeeded()
  await page.screenshot({ path: info.outputPath('desktop-dark.png') })
})

test('build panel stays above documentation and hides after acknowledgement', async ({ page }, info) => {
  await expect(page.locator('.home-result')).toHaveCount(0)
  await page.getByRole('button', { name: '构建项目', exact: true }).click()
  const panel = page.locator('.home-result')
  await expect(panel).toBeVisible()
  await expect(panel.getByRole('button', { name: '确认', exact: true })).toBeDisabled()
  await expect(panel.getByLabel('构建日志')).toContainText('Build log: compiling project')
  const panelBox = await panel.boundingBox()
  const docBox = await page.locator('.project-document').boundingBox()
  expect(panelBox!.y).toBeLessThan(docBox!.y)
  await page.screenshot({ path: info.outputPath('desktop-build.png') })
  await expect(panel.locator('.build-state')).toHaveText('完成')
  await expect(panel.getByLabel('构建日志')).toContainText('firmware ready')
  await expect(panel.locator('.elf-list')).toContainText('firmware.elf')
  await panel.getByRole('button', { name: '确认', exact: true }).click()
  await expect(panel).toHaveCount(0)
  await expect(page.locator('.project-markdown h1')).toBeVisible()
})

test('mobile layout remains contained in both themes', async ({ page }, info) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await expect(page.locator('.project-markdown h1')).toBeVisible()
  await page.screenshot({ path: info.outputPath('mobile-light.png') })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
  expect(await page.locator('.home-view').evaluate((node) => node.scrollWidth <= node.clientWidth)).toBe(true)
  await page.getByRole('button', { name: '打开导航' }).click()
  await page.getByRole('button', { name: '设置', exact: true }).click()
  await page.getByText('深色', { exact: true }).click()
  await page.getByRole('button', { name: '打开导航' }).click()
  await page.getByRole('button', { name: '项目首页', exact: true }).click()
  await expect(page.locator('[data-diagram="mermaid"] > svg')).toBeVisible()
  await page.screenshot({ path: info.outputPath('mobile-dark.png') })
  expect(await page.locator('.home-view').evaluate((node) => node.scrollWidth <= node.clientWidth)).toBe(true)
})

test('diagram failures preserve source without breaking the rest of the page', async ({ page }) => {
  await page.route('**/api/v1/workspace/document**', (route) => route.fulfill({
    json: { data: { path: 'index.md', content: '# Error isolation\n\n```mermaid\ninvalid diagram\n```\n\n```plantuml\nAlice -> Bob\n```' } },
  }))
  await page.route('https://www.plantuml.com/plantuml/svg/**', (route) => route.abort())
  await page.reload()
  await expect(page.locator('.project-markdown h1')).toHaveText('Error isolation')
  await expect(page.locator('.diagram-error')).toHaveCount(2)
  await expect(page.locator('[data-diagram="mermaid"] pre')).toBeVisible()
  await expect(page.getByRole('button', { name: '构建项目', exact: true })).toBeVisible()
})

test('online PlantUML renders real light and dark diagrams', async ({ page }, info) => {
  test.skip(process.env.ENV_WEBUI_ONLINE_DIAGRAM_TEST !== '1', 'Requires public PlantUML network access')
  test.setTimeout(60_000)
  const diagram = page.locator('[data-diagram="plantuml"] > img')
  await expect(diagram).toHaveJSProperty('complete', true)
  await page.unroute('https://www.plantuml.com/plantuml/svg/**')
  const lightResponse = page.waitForResponse((response) => response.url().startsWith('https://www.plantuml.com/plantuml/svg/'), { timeout: 25_000 })
  await page.reload()
  const light = await lightResponse
  expect(light.status()).toBe(200)
  expect(await light.text()).toContain('Alice')
  await expect(diagram).toHaveJSProperty('complete', true, { timeout: 25_000 })
  expect(await diagram.evaluate((image: HTMLImageElement) => image.naturalWidth)).toBeGreaterThan(0)
  await diagram.scrollIntoViewIfNeeded()
  await page.screenshot({ path: info.outputPath('online-plantuml-light.png') })
  await page.getByRole('button', { name: '设置', exact: true }).click()
  await page.getByText('深色', { exact: true }).click()
  const darkResponse = page.waitForResponse((response) => response.url().startsWith('https://www.plantuml.com/plantuml/svg/'), { timeout: 25_000 })
  await page.getByRole('button', { name: '项目首页', exact: true }).click()
  const dark = await darkResponse
  expect(dark.status()).toBe(200)
  expect(await dark.text()).toContain('Bob')
  await expect(diagram).toHaveJSProperty('complete', true, { timeout: 25_000 })
  expect(await diagram.evaluate((image: HTMLImageElement) => image.naturalWidth)).toBeGreaterThan(0)
  await diagram.scrollIntoViewIfNeeded()
  await page.screenshot({ path: info.outputPath('online-plantuml-dark.png') })
})
