import { expect, test } from '@playwright/test'
import { spawn, type ChildProcess } from 'node:child_process'
import { mkdtemp, readFile, rm } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { resolve } from 'node:path'

let server: ChildProcess
let launchUrl: string
let root: string

test.beforeAll(async () => {
  root = await mkdtemp(resolve(tmpdir(), 'env-network-e2e-'))
  server = spawn(process.env.PYTHON || 'python', [
    resolve(process.cwd(), '../../..', 'env.py'), 'webui', '--no-browser',
    '--env-root', root,
  ], { cwd: root, env: { ...process.env, PYTHONUNBUFFERED: '1' }, stdio: ['ignore', 'pipe', 'pipe'] })
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

test('network settings validate, persist and fit desktop/mobile screens', async ({ page }, testInfo) => {
  const errors: string[] = []
  page.on('pageerror', (error) => errors.push(error.message))
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto(launchUrl)
  await page.getByRole('button', { name: '设置', exact: true }).click()
  await page.getByRole('tab', { name: '网络', exact: true }).click()
  const settings = page.locator('.network-settings')
  await expect(settings.getByRole('button', { name: '保存网络设置' })).toBeVisible()
  await settings.getByText('自定义代理', { exact: true }).click()
  const proxy = settings.getByRole('textbox', { name: '代理地址', exact: true })
  await proxy.fill('http://user:secret@127.0.0.1:7890')
  await expect(settings.getByRole('button', { name: '保存网络设置' })).toBeDisabled()
  await proxy.fill('http://127.0.0.1:7890')
  await settings.getByRole('textbox', { name: '不使用代理的主机' }).fill('localhost,127.0.0.1,::1,.example.com')
  await settings.locator('.el-form-item').filter({ hasText: '下载服务器' }).locator('.el-select').click()
  await page.getByRole('option', { name: 'Gitee 镜像', exact: true }).click()
  await settings.locator('.el-form-item').filter({ hasText: 'Python 包索引' }).locator('.el-select').click()
  await page.getByRole('option', { name: '自定义', exact: true }).click()
  await settings.getByRole('textbox', { name: 'Python 包索引地址', exact: true }).fill('https://pypi.org/simple/')
  await settings.getByRole('spinbutton').fill('37')
  await expect(settings.getByRole('button', { name: '测试连接' })).toBeDisabled()
  await settings.getByRole('button', { name: '保存网络设置' }).click()
  await expect(page.getByText('网络设置已保存', { exact: true })).toBeVisible()
  const saved = JSON.parse(await readFile(resolve(root, 'var/network.json'), 'utf8'))
  expect(saved).toMatchObject({ proxy_mode: 'custom', proxy_url: 'http://127.0.0.1:7890',
    download_server: 'gitee', pypi_mode: 'custom', pypi_url: 'https://pypi.org/simple/', timeout: 37 })
  await page.reload()
  await page.getByRole('button', { name: '设置', exact: true }).click()
  await page.getByRole('tab', { name: '网络', exact: true }).click()
  await expect(proxy).toHaveValue('http://127.0.0.1:7890')
  await expect(settings.getByRole('spinbutton')).toHaveValue('37')
  await page.route('**/api/v1/settings/network/test', (route) => route.fulfill({
    json: { data: { target: 'github', reachable: true, status: 200, elapsed_ms: 12, message: 'HTTP 200' } },
  }))
  await settings.getByRole('button', { name: '测试连接' }).click()
  await expect(settings.getByText('连接成功 · 12 ms')).toBeVisible()
  await page.screenshot({ path: testInfo.outputPath('network-desktop.png'), fullPage: true })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true)
  await page.setViewportSize({ width: 390, height: 844 })
  await expect(settings.getByRole('button', { name: '保存网络设置' })).toBeVisible()
  await page.screenshot({ path: testInfo.outputPath('network-mobile.png'), fullPage: true })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true)
  expect(errors).toEqual([])
})
