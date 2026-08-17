import { expect, test } from '@playwright/test'
import { spawn } from 'node:child_process'
import { cp, mkdtemp, readFile, rm, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { resolve } from 'node:path'

let serverProcess
let launchUrl
let temporaryRoot
let authenticatedState
let buildInsightPackage
let buildInsightUpgradePackage
let probePackage

test.describe.configure({ mode: 'serial' })

async function run(command, args, options) {
  const child = spawn(command, args, { ...options, stdio: ['ignore', 'pipe', 'pipe'] })
  let output = ''
  child.stdout.on('data', (chunk) => { output += chunk.toString() })
  child.stderr.on('data', (chunk) => { output += chunk.toString() })
  const code = await new Promise((resolveExit) => child.once('exit', resolveExit))
  if (code !== 0) throw new Error(`${command} exited with ${code}: ${output}`)
  return output
}

test.beforeAll(async () => {
  temporaryRoot = await mkdtemp(resolve(tmpdir(), 'env-webui-e2e-'))
  const repository = resolve(process.cwd(), '../../..')
  const envScript = resolve(repository, 'env.py')
  const examples = resolve(repository, 'plugins', 'examples')
  const packages = resolve(temporaryRoot, 'packages')

  buildInsightPackage = resolve(
    examples,
    'prebuilt',
    'org.rt-thread.build-insight-1.0.0-py3-none-any.epack',
  )
  const upgradeProject = resolve(temporaryRoot, 'build-insight-1.1.0')
  await cp(resolve(examples, 'build-insight-1.0.0'), upgradeProject, { recursive: true })
  const manifestPath = resolve(upgradeProject, 'manifest.json')
  const manifest = JSON.parse(await readFile(manifestPath, 'utf8'))
  manifest.version = '1.1.0'
  await writeFile(manifestPath, `${JSON.stringify(manifest, null, 2)}\n`)
  await run('python', ['-m', 'plugins.epack.cli', 'build', upgradeProject, '-o', packages], { cwd: repository })
  buildInsightUpgradePackage = resolve(
    packages,
    'org.rt-thread.build-insight-1.1.0-py3-none-any.epack',
  )
  await run(
    'python',
    ['-m', 'plugins.epack.cli', 'build', resolve(examples, 'probe-flash-0.9.6'), '-o', packages],
    { cwd: repository },
  )
  probePackage = resolve(packages, 'org.rt-thread.probe-flash-0.9.6-py3-none-any.epack')

  serverProcess = spawn('python', [
    envScript,
    'webui',
    '--no-browser',
    '--env-root', resolve(temporaryRoot, 'env'),
  ], {
    cwd: temporaryRoot,
    env: {
      ...process.env,
      ENV_PLUGIN_LAUNCHER_DIR: resolve(temporaryRoot, 'launchers'),
      PYTHONUNBUFFERED: '1',
    },
    stdio: ['ignore', 'pipe', 'pipe'],
  })
  launchUrl = await new Promise((resolveUrl, reject) => {
    let output = ''
    const timer = setTimeout(() => reject(new Error(`env webui did not start: ${output}`)), 10_000)
    serverProcess.stdout.on('data', (chunk) => {
      output += chunk.toString()
      const match = output.match(/Launch URL: (http:\/\/[^\s]+)/)
      if (match) {
        clearTimeout(timer)
        resolveUrl(match[1])
      }
    })
    serverProcess.stderr.on('data', (chunk) => { output += chunk.toString() })
    serverProcess.on('exit', (code) => {
      clearTimeout(timer)
      reject(new Error(`env webui exited with ${code}: ${output}`))
    })
  })
})

test.afterAll(async () => {
  if (serverProcess && serverProcess.exitCode === null) {
    serverProcess.kill('SIGINT')
    await new Promise((resolveExit) => serverProcess.once('exit', resolveExit))
  }
  if (temporaryRoot) await rm(temporaryRoot, { recursive: true, force: true })
})

test('desktop installs and opens a local WebUI package', async ({ browser }) => {
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } })
  const page = await context.newPage()
  const consoleErrors = []
  page.on('console', (message) => {
    if (message.type() === 'error') consoleErrors.push(message.text())
  })
  await page.goto(launchUrl)
  await expect(page.getByRole('heading', { name: '插件中心' })).toBeVisible()
  await expect(page.getByRole('tab', { name: '本地安装' })).toBeVisible()
  await expect(page.getByRole('tab', { name: '在线插件' })).toHaveCount(0)
  await expect(page.getByRole('tab', { name: '发现插件' })).toHaveCount(0)
  await expect(page.getByText('工作台', { exact: true })).toHaveCount(0)
  await expect(page.getByText('终端', { exact: true })).toHaveCount(0)
  await expect(page.getByText('任务', { exact: true })).toHaveCount(0)

  await page.locator('.local-upload-zone input[type="file"]').setInputFiles(buildInsightPackage)
  await expect(page.locator('.package-review').getByRole('heading', { name: 'Build Insight' })).toBeVisible()
  await page.locator('.package-review').getByText('我已确认来源并接受未签名包风险', { exact: true }).click()
  await page.getByRole('button', { name: '安装本地包' }).click()

  const buildCard = page.locator('.installed-card').filter({ hasText: 'Build Insight' })
  await expect(buildCard).toBeVisible()
  await buildCard.getByRole('button', { name: '详情' }).click()
  await expect(page.getByRole('dialog').getByRole('heading', { name: 'Build Insight' })).toBeVisible()
  await page.getByRole('dialog').getByRole('button', { name: '关闭', exact: true }).click()
  await buildCard.getByRole('button', { name: '打开' }).click()

  const pluginFrame = page.locator('iframe[title="Build Insight"]')
  await expect(pluginFrame).toBeVisible()
  await expect(pluginFrame.contentFrame().getByRole('heading', { name: '固件构建分析' })).toBeVisible()
  await expect(pluginFrame.contentFrame().getByText('SDK 1.0.0')).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true)
  expect(consoleErrors).toEqual([])
  authenticatedState = await context.storageState()
  await context.close()
})

test('permissions, local upgrade and CLI package import stay synchronized', async ({ browser }) => {
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, storageState: authenticatedState })
  const page = await context.newPage()
  await page.goto(new URL('/', launchUrl).toString())
  await page.getByRole('tab', { name: '已安装' }).click()
  let buildCard = page.locator('.installed-card').filter({ hasText: 'Build Insight' })
  await buildCard.getByRole('button', { name: '管理' }).click()
  await page.getByText('读取工作区', { exact: true }).click()
  await page.getByRole('button', { name: '保存权限' }).click()
  await page.keyboard.press('Escape')

  await page.locator('.nav-entry').filter({ hasText: 'Build Insight' }).click()
  await expect(page.getByRole('heading', { name: '需要恢复权限' })).toBeVisible()
  await page.getByRole('button', { name: '管理权限' }).click()
  await page.getByText('读取工作区', { exact: true }).click()
  await page.getByRole('button', { name: '保存权限' }).click()
  await page.getByRole('button', { name: '运行诊断' }).click()
  await expect(page.getByText('诊断通过')).toBeVisible()
  await page.getByRole('button', { name: '从本地包更新' }).click()

  const upgradeDialog = page.getByRole('dialog', { name: '从本地包更新' })
  await upgradeDialog.locator('.upload-zone input[type="file"]').setInputFiles(buildInsightUpgradePackage)
  await expect(upgradeDialog.getByText('Build Insight · v1.1.0')).toBeVisible()
  await upgradeDialog.getByText('我已确认来源并接受未签名包风险', { exact: true }).click()
  await upgradeDialog.getByRole('button', { name: '确认更新' }).click()

  await page.locator('.sidebar-footer').getByText('插件中心', { exact: true }).click()
  await page.getByRole('tab', { name: '已安装' }).click()
  buildCard = page.locator('.installed-card').filter({ hasText: 'Build Insight' })
  await expect(buildCard.getByText('v1.1.0')).toBeVisible()
  await page.getByRole('tab', { name: '本地安装' }).click()
  await page.locator('.local-upload-zone input[type="file"]').setInputFiles(probePackage)
  await expect(page.locator('.package-review').getByRole('heading', { name: 'Probe & Flash' })).toBeVisible()
  await page.locator('.package-review').getByText('我已确认来源并接受未签名包风险', { exact: true }).click()
  await page.getByRole('button', { name: '安装本地包' }).click()
  await expect(page.locator('.installed-card').filter({ hasText: 'Probe & Flash' })).toBeVisible()
  await expect(page.locator('.plugin-navigation').getByText('Probe & Flash', { exact: true })).toHaveCount(0)
  authenticatedState = await context.storageState()
  await context.close()
})

test('mobile navigation keeps local plugin management above settings', async ({ browser }) => {
  const context = await browser.newContext({ viewport: { width: 390, height: 844 }, storageState: authenticatedState })
  const page = await context.newPage()
  await page.goto(new URL('/', launchUrl).toString())
  await page.getByRole('button', { name: '打开导航' }).click()
  const footer = page.locator('.sidebar-footer')
  const order = await footer.locator('.nav-entry').allTextContents()
  expect(order[0]).toContain('插件中心')
  expect(order[1]).toContain('设置')
  await footer.getByText('插件中心', { exact: true }).click()
  await expect(page.getByRole('tab', { name: '本地安装' })).toBeVisible()
  await page.getByRole('tab', { name: '已安装' }).click()
  await expect(page.locator('.plugin-grid .plugin-card:visible')).toHaveCount(2)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true)
  await context.close()
})
