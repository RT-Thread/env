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

test('SDK settings previews and applies a toolchain change', async ({ browser }) => {
  const contextOptions = { viewport: { width: 1440, height: 900 } }
  if (authenticatedState) contextOptions.storageState = authenticatedState
  const context = await browser.newContext(contextOptions)
  const page = await context.newPage()
  const disabledSnapshot = {
    available: true,
    platform: 'Linux',
    packages_root: '/tmp/env/packages',
    index_root: '/tmp/env/packages/sdk/Linux',
    config_path: '/tmp/env/tools/scripts/.config',
    revision: 'r1',
    config_revision: 'r1',
    packages: [{
      name: 'demo-gcc',
      description: '演示工具链',
      enabled: false,
      expected_version: null,
      installed_version: null,
      state: 'disabled',
      versions: [{ version: 'v1', url: 'https://example.invalid/demo-v1.tar.gz', filename: 'demo-v1.tar.gz' }],
    }],
  }
  const installedSnapshot = {
    ...disabledSnapshot,
    packages: [{
      ...disabledSnapshot.packages[0],
      enabled: true,
      expected_version: 'v1',
      installed_version: 'v1',
      state: 'installed',
    }],
  }
  let taskSnapshot = installedSnapshot
  let taskPlanId = 'install-plan'
  let taskPollCount = 0
  let taskCancelled = false
  await page.route('**/api/v1/sdk', async (route) => {
    await route.fulfill({ json: { data: disabledSnapshot } })
  })
  await page.route('**/api/v1/sdk/plan', async (route) => {
    const selection = route.request().postDataJSON().packages[0]
    const removing = !selection.enabled
    await route.fulfill({
      json: {
        data: {
          plan_id: removing ? 'remove-plan' : 'install-plan',
          revision: 'r1',
          config_revision: 'r1',
          operations: removing
            ? [{ action: 'remove', name: 'demo-gcc', version: 'v1' }]
            : [{ action: 'install', name: 'demo-gcc', from_version: null, to_version: 'v1' }],
          remove_confirmation: removing ? ['demo-gcc'] : [],
          snapshot: removing ? installedSnapshot : disabledSnapshot,
        },
      },
    })
  })
  await page.route('**/api/v1/sdk/apply', async (route) => {
    const request = route.request().postDataJSON()
    taskPlanId = request.plan_id
    taskPollCount = 0
    taskCancelled = false
    taskSnapshot = taskPlanId === 'remove-plan' ? disabledSnapshot : installedSnapshot
    if (taskPlanId === 'remove-plan') expect(request.confirm_remove).toEqual(['demo-gcc'])
    await route.fulfill({
      status: 202,
      json: { data: { task_id: 'task-e2e', plan_id: taskPlanId, status: 'queued', stage: 'queued', progress: 0, error: null } },
    })
  })
  await page.route('**/api/v1/sdk/tasks/**', async (route) => {
    if (route.request().method() === 'POST' && route.request().url().endsWith('/cancel')) {
      taskCancelled = true
      await route.fulfill({
        status: 202,
        json: {
          data: {
            task_id: 'task-e2e',
            plan_id: taskPlanId,
            status: 'cancelled',
            stage: 'cancelled',
            progress: 12,
            message: '更新已取消，临时变更已回滚',
            downloaded_bytes: 1048576,
            total_bytes: 8388608,
            download_speed: 524288,
            operation_index: 1,
            operation_total: 1,
            operations: [{ action: 'install', name: 'demo-gcc', to_version: 'v1', status: 'cancelled', stage: 'cancelled', progress: 12, message: '更新已取消，临时变更已回滚', downloaded_bytes: 1048576, total_bytes: 8388608, download_speed: 524288 }],
            error: null,
          },
        },
      })
      return
    }
    taskPollCount += 1
    if (taskCancelled) {
      await route.fulfill({
        json: {
          data: {
            task_id: 'task-e2e',
            plan_id: taskPlanId,
            status: 'cancelled',
            stage: 'cancelled',
            progress: 12,
            message: '更新已取消，临时变更已回滚',
            downloaded_bytes: 1048576,
            total_bytes: 8388608,
            download_speed: 524288,
            operation_index: 1,
            operation_total: 1,
            operations: [{ action: 'install', name: 'demo-gcc', to_version: 'v1', status: 'cancelled', stage: 'cancelled', progress: 12, message: '更新已取消，临时变更已回滚', downloaded_bytes: 1048576, total_bytes: 8388608, download_speed: 524288 }],
            error: null,
          },
        },
      })
      return
    }
    if (taskPollCount <= 3) {
      if (taskPollCount === 1) await new Promise((resolve) => setTimeout(resolve, 420))
      const installing = taskPlanId !== 'remove-plan'
      await route.fulfill({
        json: {
          data: {
            task_id: 'task-e2e',
            plan_id: taskPlanId,
            status: 'running',
            stage: installing ? 'downloading' : 'writing_config',
            progress: installing ? 12 : 92,
            message: installing ? '正在下载 demo-gcc v1' : '正在写入 .config 和 SDK 包状态（共 1 项操作）',
            downloaded_bytes: installing ? 1048576 : 0,
            total_bytes: installing ? 8388608 : null,
            download_speed: installing ? 524288 : 0,
            current_package: installing ? 'demo-gcc' : null,
            current_version: installing ? 'v1' : null,
            current_action: installing ? 'install' : 'write_config',
            operation_index: 1,
            operation_total: 1,
            operations: [{
              action: installing ? 'install' : 'remove',
              name: 'demo-gcc',
              from_version: installing ? null : 'v1',
              to_version: installing ? 'v1' : null,
              version: installing ? null : 'v1',
              status: 'running',
              stage: installing ? 'downloading' : 'writing_config',
              progress: installing ? 12 : 92,
              message: installing ? '正在下载 demo-gcc v1' : '正在写入配置',
              downloaded_bytes: installing ? 1048576 : 0,
              total_bytes: installing ? 8388608 : null,
              download_speed: installing ? 524288 : 0,
            }],
            error: null,
          },
        },
      })
      return
    }
    await route.fulfill({
      json: {
        data: {
          task_id: 'task-e2e',
          plan_id: taskPlanId,
          status: 'succeeded',
          stage: 'completed',
          progress: 100,
          message: 'SDK 更新完成，共 1 项操作',
          downloaded_bytes: taskPlanId === 'remove-plan' ? 0 : 8388608,
          total_bytes: taskPlanId === 'remove-plan' ? null : 8388608,
          download_speed: taskPlanId === 'remove-plan' ? 0 : 524288,
          operation_index: 1,
          operation_total: 1,
          operations: [{ action: taskPlanId === 'remove-plan' ? 'remove' : 'install', name: 'demo-gcc', version: 'v1', to_version: taskPlanId === 'remove-plan' ? null : 'v1', status: 'succeeded', stage: 'completed', progress: 100, message: '已完成' }],
          error: null,
          snapshot: taskSnapshot,
        },
      },
    })
  })

  await page.goto(authenticatedState ? new URL('/', launchUrl).toString() : launchUrl)
  await page.locator('.sidebar-footer').getByText('设置', { exact: true }).click()
  await page.getByRole('tab', { name: 'SDK 管理' }).click()
  await expect(page.getByRole('heading', { name: 'demo-gcc' })).toBeVisible()
  await expect(page.getByText('Env 会根据使用的工具链命令名称，自动从已安装的工具链中探测并使用匹配项。', { exact: true })).toBeVisible()
  await page.locator('.sdk-list-row .el-checkbox').click()
  const previewButton = page.locator('.sdk-toolbar .sdk-primary-action')
  const previewImmediateStyle = await previewButton.evaluate((element) => {
    const computed = getComputedStyle(element)
    return { color: computed.color, transitionProperty: computed.transitionProperty }
  })
  expect(previewImmediateStyle.color).toBe('rgb(255, 255, 255)')
  expect(previewImmediateStyle.transitionProperty.split(',').map((property) => property.trim())).not.toContain('color')
  await expect(previewButton).toHaveCSS('background-color', 'rgb(15, 118, 110)')
  await expect(previewButton).toHaveCSS('color', 'rgb(255, 255, 255)')
  await page.getByRole('button', { name: '预览变更' }).click()
  await expect(page.getByText('demo-gcc · 安装 v1')).toBeVisible()
  const applyButton = page.getByRole('button', { name: '应用更新' })
  await expect(applyButton).toBeEnabled()
  await expect(applyButton).toHaveCSS('background-color', 'rgb(15, 118, 110)')
  await expect(applyButton).toHaveCSS('border-color', 'rgb(15, 118, 110)')
  await expect(applyButton).toHaveCSS('color', 'rgb(255, 255, 255)')
  await expect(applyButton).toHaveCSS('transition-property', 'background-color, border-color, box-shadow, opacity')
  await page.getByRole('button', { name: '切换主题' }).click()
  await expect(previewButton).toHaveCSS('background-color', 'rgb(115, 214, 203)')
  await expect(previewButton).toHaveCSS('color', 'rgb(16, 37, 34)')
  await expect(applyButton).toHaveCSS('background-color', 'rgb(115, 214, 203)')
  await expect(applyButton).toHaveCSS('border-color', 'rgb(115, 214, 203)')
  await expect(applyButton).toHaveCSS('color', 'rgb(16, 37, 34)')
  const applyPromise = applyButton.click()
  await expect(page.locator('.sdk-task-message').filter({ hasText: '正在下载 demo-gcc v1' })).toBeVisible()
  await expect(page.locator('.sdk-task-download').getByText('下载 1 MB / 8 MB')).toBeVisible()
  await expect(page.locator('.sdk-task-download').getByText('速度 512 KB/s')).toBeVisible()
  await expect(page.getByText('操作 1 / 1')).toBeVisible()
  await expect(page.getByRole('button', { name: '取消更新' })).toBeVisible()
  await page.getByRole('button', { name: '取消更新' }).click()
  await expect(page.getByText('更新已取消', { exact: true })).toBeVisible()
  await applyPromise
  await expect(applyButton).toBeEnabled()
  await applyButton.click()
  await expect(page.getByText('更新完成', { exact: true })).toBeVisible()
  await expect(page.getByText('实际 v1')).toBeVisible()

  await page.locator('.sdk-list-row .el-checkbox').click()
  await page.getByRole('button', { name: '预览变更' }).click()
  await expect(page.getByText('demo-gcc · 移除 v1')).toBeVisible()
  await page.getByRole('button', { name: '应用更新' }).click()
  await expect(page.getByText('确认删除 SDK 包')).toBeVisible()
  await page.getByRole('button', { name: '确认删除' }).click()
  await expect(page.getByText('实际 未安装')).toBeVisible()
  await context.close()
})

test('local toolchain settings manage sdk_cfg.json', async ({ browser }) => {
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, storageState: authenticatedState })
  const page = await context.newPage()
  await page.goto(new URL('/', launchUrl).toString())
  await page.locator('.sidebar-footer').getByText('设置', { exact: true }).click()
  await expect(page.getByText('文件资源管理器右键菜单', { exact: true })).toHaveCount(0)
  await page.getByRole('tab', { name: '本地工具链配置' }).click()
  await expect(page.getByText('sdk_cfg.json', { exact: false })).toBeVisible()
  await expect(page.getByText('Env 会优先使用名称匹配的工具链。', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: '添加工具链' }).click()
  const dialog = page.getByRole('dialog', { name: '添加本地工具链' })
  await dialog.getByLabel('名称').fill('demo-gcc')
  await dialog.getByLabel('工具链路径').fill('/tmp/demo-gcc/bin')
  await dialog.getByLabel('说明').fill('测试工具链')
  await dialog.getByRole('button', { name: '保存配置' }).click()
  await expect(page.locator('.toolchain-list-row').getByText('demo-gcc', { exact: true })).toBeVisible()
  await page.locator('.toolchain-list-row').getByRole('button', { name: '编辑' }).click()
  const editDialog = page.getByRole('dialog', { name: '编辑本地工具链' })
  await editDialog.getByLabel('工具链路径').fill('/tmp/demo-gcc-updated/bin')
  await editDialog.getByRole('button', { name: '保存修改' }).click()
  await expect(page.locator('.toolchain-list-row').getByText('/tmp/demo-gcc-updated/bin', { exact: true })).toBeVisible()
  await page.locator('.toolchain-list-row').getByRole('button', { name: '删除' }).click()
  await expect(page.getByText('确认删除工具链配置')).toBeVisible()
  await page.getByRole('button', { name: '确认删除' }).click()
  await expect(page.getByText('尚未配置本地工具链')).toBeVisible()
  await context.close()
})
