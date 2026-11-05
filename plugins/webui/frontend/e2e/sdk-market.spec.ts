import { expect, test } from '@playwright/test'
import { spawn, type ChildProcess } from 'node:child_process'
import { createHash } from 'node:crypto'
import { mkdir, mkdtemp, readFile, rm, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { resolve } from 'node:path'

let server: ChildProcess
let launchUrl: string
let root: string
let indexPath: string

test.beforeAll(async () => {
  root = await mkdtemp(resolve(tmpdir(), 'env-sdk-market-e2e-'))
  const repository = resolve(process.cwd(), '../../..')
  const example = resolve(repository, 'plugins/examples/build-insight-1.0.0')
  const manifest = JSON.parse(await readFile(resolve(example, 'manifest.json'), 'utf8'))
  const content = await readFile(resolve(repository,
    'plugins/examples/prebuilt/org.rt-thread.build-insight-1.0.0-py3-none-any.epack'))
  const indexRoot = resolve(root, 'packages/sdk/env-plugins')
  const pluginRoot = resolve(indexRoot, manifest.id)
  await mkdir(pluginRoot, { recursive: true })
  indexPath = resolve(indexRoot, 'index.json')
  await writeFile(indexPath, JSON.stringify({ version: 1, index: [manifest.id] }))
  const plugin = {
    id: manifest.id, name: manifest.name, description: manifest.description,
    capabilities: ['commands', 'webui'], versions: [{
      version: manifest.version, artifacts: [{
        filename: 'build-insight.epack',
        url: 'https://github.com/example/plugins/releases/download/v1.0.0/build-insight.epack',
        sha256: createHash('sha256').update(content).digest('hex'),
        size_bytes: content.length, compatibility: manifest.compatibility,
      }],
    }],
  }
  await writeFile(resolve(pluginRoot, 'index.json'), JSON.stringify(plugin))
  server = spawn(process.env.PYTHON || 'python', [
    resolve(repository, 'env.py'), 'webui', '--no-browser', '--env-root', root,
  ], {
    cwd: root,
    env: { ...process.env, ENV_PLUGIN_MARKET_URL: '', PYTHONUNBUFFERED: '1' },
    stdio: ['ignore', 'pipe', 'pipe'],
  })
  launchUrl = await new Promise<string>((resolveUrl, reject) => {
    let output = ''
    const timer = setTimeout(() => reject(new Error(`WebUI startup timeout: ${output}`)), 10_000)
    server.stdout!.on('data', (chunk) => {
      output += chunk.toString()
      const match = output.match(/Launch URL: (http:\/\/[^\s]+)/)
      if (match) { clearTimeout(timer); resolveUrl(match[1]) }
    })
    server.stderr!.on('data', (chunk) => { output += chunk.toString() })
    server.once('exit', (code) => { clearTimeout(timer); reject(new Error(`WebUI exited ${code}: ${output}`)) })
  })
})

test.afterAll(async () => {
  if (server && server.exitCode === null) {
    server.kill('SIGINT')
    await new Promise((resolveExit) => server.once('exit', resolveExit))
  }
  if (root) await rm(root, { recursive: true, force: true })
})

test('SDK catalog is discovered, refreshed and labeled on desktop and mobile', async ({ page }, testInfo) => {
  const errors: string[] = []
  const externalRequests: string[] = []
  page.on('pageerror', (error) => errors.push(error.message))
  page.on('request', (request) => {
    if (new URL(request.url()).hostname === 'github.com') externalRequests.push(request.url())
  })
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto(launchUrl)
  await page.getByRole('button', { name: '插件中心', exact: true }).click()
  await page.getByRole('tab', { name: '在线插件', exact: true }).click()
  const card = page.locator('.market-card').filter({ hasText: 'Build Insight' })
  await expect(card).toBeVisible()
  await card.getByRole('button', { name: '详情', exact: true }).click()
  const dialog = page.getByRole('dialog')
  await expect(dialog.getByText('当前环境可以安装', { exact: true })).toBeVisible()
  await dialog.getByRole('button', { name: '关闭', exact: true }).click()
  await page.screenshot({ path: testInfo.outputPath('sdk-market-desktop.png'), fullPage: true })
  await page.getByRole('button', { name: '设置', exact: true }).click()
  await expect(page.getByText(`${indexPath} · SDK 仓库索引`, { exact: true })).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true)
  await page.setViewportSize({ width: 390, height: 844 })
  await expect(page.getByText(`${indexPath} · SDK 仓库索引`, { exact: true })).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true)
  await page.getByRole('button', { name: '打开导航', exact: true }).click()
  await page.getByRole('button', { name: '插件中心', exact: true }).click()
  await page.getByRole('tab', { name: '在线插件', exact: true }).click()
  await expect(card).toBeVisible()
  await page.screenshot({ path: testInfo.outputPath('sdk-market-mobile.png'), fullPage: true })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true)
  await writeFile(indexPath, JSON.stringify({ version: 1, index: [] }))
  await page.getByRole('button', { name: '刷新目录', exact: true }).click()
  await expect(page.getByText('目录为空', { exact: true })).toBeVisible()
  expect(errors).toEqual([])
  expect(externalRequests).toEqual([])
})
