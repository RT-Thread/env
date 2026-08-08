<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import {
  ArrowUp,
  Box,
  CircleCheck,
  Close,
  Cpu,
  DataAnalysis,
  Delete,
  Grid,
  InfoFilled,
  Lock,
  Menu,
  Moon,
  MoreFilled,
  Operation,
  Platform,
  Refresh,
  Setting,
  Sunny,
  SwitchButton,
  Tools,
  UploadFilled,
  WarningFilled,
} from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { api, setCsrfToken } from './api.js'

const session = ref(null)
const installed = ref([])
const loading = ref(true)
const actionBusy = ref(false)
const sidebarOpen = ref(false)
const currentView = ref('plugins')
const pluginTab = ref('local')
const theme = ref(localStorage.getItem('env-theme') || 'light')
const detailVisible = ref(false)
const detailPlugin = ref(null)
const importFile = ref(null)
const importSummary = ref(null)
const importUnsignedConsent = ref(false)
const importStage = ref('选择本地包')
const upgradeVisible = ref(false)
const upgradeTarget = ref(null)
const upgradeFile = ref(null)
const upgradeSummary = ref(null)
const upgradeUnsignedConsent = ref(false)
const upgradeStage = ref('选择本地包')
const manageVisible = ref(false)
const managedPlugin = ref(null)
const permissionSelection = ref([])
const diagnostic = ref(null)
const uninstallVisible = ref(false)
const purgeData = ref(false)
const iframeState = ref('idle')
const iframeElement = ref(null)
let iframeTimer

const permissionLabels = {
  'workspace.read': '读取工作区',
  'workspace.write': '读写工作区',
  'process.execute': '执行本机进程',
  'network.access': '访问网络',
  'credentials.use': '使用凭据',
  'device.serial': '访问串行设备',
}

const iconMap = {
  'chart-no-axes-combined': DataAnalysis,
  'shield-check': Lock,
  cpu: Cpu,
  tools: Tools,
}

const navigablePlugins = computed(() => installed.value.filter((item) => item.enabled && item.webui))
const activePlugin = computed(() => installed.value.find((item) => item.id === currentView.value))
const upgradeMismatch = computed(() => (
  upgradeSummary.value && upgradeTarget.value && upgradeSummary.value.id !== upgradeTarget.value.id
))

function iconFor(plugin) {
  return iconMap[plugin?.webui?.icon] || (plugin?.commands?.length ? Tools : Box)
}

function compatibilityText(plugin) {
  if (plugin.compatibility_issues?.length) return plugin.compatibility_issues[0]
  const platforms = plugin.compatibility?.platforms || []
  return platforms.includes('any') ? 'Windows · Linux · macOS' : platforms.join(' · ')
}

function commandNames(plugin) {
  return (plugin.commands || []).map((command) => (
    typeof command === 'string' ? command : command.name
  ))
}

function commandDescription(command) {
  return typeof command === 'string' ? '插件命令入口' : command.description
}

async function bootstrap() {
  loading.value = true
  try {
    session.value = await api.session()
    setCsrfToken(session.value.csrf_token)
    await reloadAll()
  } catch (error) {
    ElMessage.error(error.message)
  } finally {
    loading.value = false
  }
}

async function reloadAll() {
  const installedItems = await api.plugins()
  installed.value = installedItems
  if (currentView.value !== 'plugins' && currentView.value !== 'settings') {
    const current = installedItems.find((item) => item.id === currentView.value)
    if (!current?.enabled || !current.webui) currentView.value = 'plugins'
  }
}

watch(theme, (value) => {
  document.documentElement.dataset.theme = value
  localStorage.setItem('env-theme', value)
  sendPluginContext()
}, { immediate: true })

function go(view) {
  currentView.value = view
  sidebarOpen.value = false
  if (view !== 'plugins' && view !== 'settings') {
    iframeState.value = 'checking'
    api.doctor(view).then((result) => {
      if (currentView.value !== view) return
      if (result.status !== 'ok') {
        iframeState.value = 'error'
        return
      }
      iframeState.value = 'loading'
      window.clearTimeout(iframeTimer)
      iframeTimer = window.setTimeout(() => {
        if (iframeState.value === 'loading') iframeState.value = 'timeout'
      }, 8000)
    }).catch(() => {
      if (currentView.value === view) iframeState.value = 'error'
    })
  }
}

function showDetail(plugin) {
  detailPlugin.value = plugin
  detailVisible.value = true
}

function beginUpdate(plugin) {
  upgradeTarget.value = plugin
  upgradeFile.value = null
  upgradeSummary.value = null
  upgradeUnsignedConsent.value = false
  upgradeStage.value = '选择本地包'
  manageVisible.value = false
  upgradeVisible.value = true
}

async function selectImport(event) {
  const file = event.target.files?.[0]
  event.target.value = ''
  if (!file) return
  if (!file.name.toLowerCase().endsWith('.epack')) {
    ElMessage.error('请选择 .epack 插件包')
    return
  }
  importFile.value = file
  importSummary.value = null
  importUnsignedConsent.value = false
  importStage.value = '检查结构、完整性与兼容性'
  actionBusy.value = true
  try {
    importSummary.value = await api.uploadPackage(file)
    importStage.value = '检查通过，等待确认'
  } catch (error) {
    importStage.value = '检查失败'
    ElMessage.error(error.message)
  } finally {
    actionBusy.value = false
  }
}

async function confirmImport() {
  if (!importSummary.value || (importSummary.value.signing_status === 'unsigned' && !importUnsignedConsent.value)) return
  actionBusy.value = true
  importStage.value = '安装后端并注册前端资源'
  try {
    const result = await api.installUpload(importSummary.value.upload_id, importUnsignedConsent.value)
    importStage.value = '状态已提交到 Env Core'
    await reloadAll()
    pluginTab.value = 'installed'
    ElMessage.success(`${result.name} 已安装`)
  } catch (error) {
    importStage.value = '安装失败，请重新选择插件包'
    importSummary.value = null
    ElMessage.error(error.message)
  } finally {
    actionBusy.value = false
  }
}

async function selectUpgrade(event) {
  const file = event.target.files?.[0]
  event.target.value = ''
  if (!file) return
  if (!file.name.toLowerCase().endsWith('.epack')) {
    ElMessage.error('请选择 .epack 插件包')
    return
  }
  upgradeFile.value = file
  upgradeSummary.value = null
  upgradeUnsignedConsent.value = false
  upgradeStage.value = '检查结构、完整性与兼容性'
  actionBusy.value = true
  try {
    upgradeSummary.value = await api.uploadPackage(file)
    upgradeStage.value = upgradeMismatch.value ? '插件标识与已安装插件不一致' : '检查通过，等待确认'
  } catch (error) {
    upgradeStage.value = '检查失败'
    ElMessage.error(error.message)
  } finally {
    actionBusy.value = false
  }
}

async function confirmUpgrade() {
  if (!upgradeSummary.value || upgradeMismatch.value) return
  if (upgradeSummary.value.signing_status === 'unsigned' && !upgradeUnsignedConsent.value) return
  actionBusy.value = true
  upgradeStage.value = '安装新版本并切换状态'
  try {
    const result = await api.upgradeUpload(
      upgradeTarget.value.id,
      upgradeSummary.value.upload_id,
      upgradeUnsignedConsent.value,
    )
    upgradeStage.value = '状态已提交到 Env Core'
    await reloadAll()
    upgradeVisible.value = false
    managedPlugin.value = installed.value.find((item) => item.id === result.id)
    ElMessage.success(`${result.name} 已更新到 v${result.version}`)
  } catch (error) {
    upgradeStage.value = '更新失败，请重新选择插件包'
    upgradeSummary.value = null
    ElMessage.error(error.message)
  } finally {
    actionBusy.value = false
  }
}

function openManage(plugin) {
  managedPlugin.value = plugin
  permissionSelection.value = [...plugin.granted_permissions]
  diagnostic.value = null
  manageVisible.value = true
}

async function savePermissions() {
  actionBusy.value = true
  try {
    await api.setPermissions(managedPlugin.value.id, permissionSelection.value)
    await reloadAll()
    managedPlugin.value = installed.value.find((item) => item.id === managedPlugin.value.id)
    ElMessage.success('权限已同步到 Env Core')
  } catch (error) {
    ElMessage.error(error.message)
  } finally {
    actionBusy.value = false
  }
}

async function runDoctor(plugin) {
  actionBusy.value = true
  try {
    diagnostic.value = await api.doctor(plugin.id)
  } catch (error) {
    ElMessage.error(error.message)
  } finally {
    actionBusy.value = false
  }
}

async function togglePlugin(plugin) {
  actionBusy.value = true
  try {
    await api.setEnabled(plugin.id, !plugin.enabled)
    await reloadAll()
    ElMessage.success(plugin.enabled ? `${plugin.name} 已禁用` : `${plugin.name} 已启用`)
  } catch (error) {
    ElMessage.error(error.message)
  } finally {
    actionBusy.value = false
  }
}

function confirmUninstall(plugin) {
  managedPlugin.value = plugin
  purgeData.value = false
  uninstallVisible.value = true
}

async function uninstallPlugin() {
  actionBusy.value = true
  try {
    const name = managedPlugin.value.name
    await api.uninstall(managedPlugin.value.id, purgeData.value)
    manageVisible.value = false
    uninstallVisible.value = false
    await reloadAll()
    ElMessage.success(`${name} 已卸载`)
  } catch (error) {
    ElMessage.error(error.message)
  } finally {
    actionBusy.value = false
  }
}

function sendPluginContext() {
  if (!iframeElement.value?.contentWindow || !activePlugin.value) return
  iframeElement.value.contentWindow.postMessage({
    type: 'env.host.context',
    payload: {
      pluginId: activePlugin.value.id,
      sdkVersion: session.value?.frontend_sdk || '1.0.0',
      theme: theme.value,
      language: 'zh-CN',
    },
  }, '*')
}

function iframeLoaded() {
  iframeState.value = 'ready'
  window.clearTimeout(iframeTimer)
  nextTick(sendPluginContext)
}

function receivePluginMessage(event) {
  if (event.source !== iframeElement.value?.contentWindow) return
  if (event.data?.type === 'env.host.ready') {
    iframeState.value = 'ready'
    sendPluginContext()
  } else if (event.data?.type === 'env.host.error') {
    iframeState.value = 'error'
  }
}

onMounted(() => {
  window.addEventListener('message', receivePluginMessage)
  bootstrap()
})

onBeforeUnmount(() => {
  window.removeEventListener('message', receivePluginMessage)
  window.clearTimeout(iframeTimer)
})
</script>

<template>
  <el-config-provider>
    <div class="app-shell" :class="{ 'sidebar-open': sidebarOpen }" v-loading="loading">
      <aside class="sidebar">
        <div class="brand">
          <span class="brand-mark">RT</span>
          <div><strong>RT-Thread Env</strong><small>Plugin Platform</small></div>
          <el-button class="mobile-close" text circle :icon="Close" aria-label="关闭导航" @click="sidebarOpen = false" />
        </div>

        <nav class="plugin-navigation" aria-label="已安装插件">
          <div class="nav-heading"><span>已安装插件</span><b>{{ navigablePlugins.length }}</b></div>
          <button
            v-for="plugin in navigablePlugins"
            :key="plugin.id"
            class="nav-entry"
            :class="{ active: currentView === plugin.id }"
            @click="go(plugin.id)"
          >
            <span class="nav-icon"><component :is="iconFor(plugin)" /></span>
            <span>{{ plugin.name }}</span>
            <i v-if="plugin.missing_required_permissions.length" class="nav-warning" title="需要恢复权限"></i>
          </button>
          <div v-if="!navigablePlugins.length" class="nav-empty">尚无可打开的插件</div>
        </nav>

        <div class="sidebar-footer">
          <button class="nav-entry footer-entry" :class="{ active: currentView === 'plugins' }" @click="go('plugins')">
            <span class="nav-icon"><Grid /></span><span>插件中心</span>
          </button>
          <button class="nav-entry" :class="{ active: currentView === 'settings' }" @click="go('settings')">
            <span class="nav-icon"><Setting /></span><span>设置</span>
          </button>
        </div>
      </aside>

      <button class="mobile-scrim" aria-label="关闭导航" @click="sidebarOpen = false"></button>

      <main class="main-shell">
        <header class="topbar">
          <el-button class="mobile-menu" text circle :icon="Menu" aria-label="打开导航" @click="sidebarOpen = true" />
          <div class="topbar-spacer"></div>
          <span class="core-status"><i></i>Env Core 已连接</span>
          <el-tooltip :content="theme === 'light' ? '切换深色主题' : '切换浅色主题'">
            <el-button text circle :icon="theme === 'light' ? Moon : Sunny" aria-label="切换主题" @click="theme = theme === 'light' ? 'dark' : 'light'" />
          </el-tooltip>
          <span class="avatar">ENV</span>
        </header>

        <section v-if="currentView === 'plugins'" class="content-scroll plugin-center-view">
          <div class="page-header">
            <div><h1>插件中心</h1><p>从本机安装和管理 Env 插件</p></div>
            <div class="page-actions">
              <el-tooltip content="刷新插件状态"><el-button :icon="Refresh" circle aria-label="刷新插件状态" @click="reloadAll" /></el-tooltip>
            </div>
          </div>

          <el-tabs v-model="pluginTab" class="plugin-tabs">
            <el-tab-pane label="本地安装" name="local">
              <div class="local-install-panel">
                <label class="upload-zone local-upload-zone">
                  <input type="file" accept=".epack" @change="selectImport">
                  <UploadFilled />
                  <strong>{{ importFile?.name || '选择本地 .epack' }}</strong>
                  <span>{{ importStage }}</span>
                </label>
                <div v-if="importSummary" class="package-review">
                  <div class="package-review-heading">
                    <span class="plugin-icon"><component :is="iconFor(importSummary)" /></span>
                    <div>
                      <h2>{{ importSummary.name }}</h2>
                      <p>{{ importSummary.author.name }} · v{{ importSummary.version }}</p>
                    </div>
                    <span class="state" :class="importSummary.compatibility_issues.length ? 'incompatible' : 'open'">
                      {{ importSummary.compatibility_issues.length ? '不兼容' : '检查通过' }}
                    </span>
                  </div>
                  <p class="description">{{ importSummary.description }}</p>
                  <div class="metadata package-metadata">
                    <span>{{ importSummary.webui ? 'WebUI' : 'CLI' }}</span>
                    <span>{{ commandNames(importSummary).join(' · ') || '无命令入口' }}</span>
                    <span>{{ compatibilityText(importSummary) }}</span>
                  </div>
                  <div class="permission-review compact-review">
                    <div v-if="importSummary.webui"><Platform /><span><strong>WebUI 页面</strong><small>{{ importSummary.webui.entry }}</small></span></div>
                    <div v-for="permission in importSummary.permissions" :key="permission.name"><Lock /><span><strong>{{ permissionLabels[permission.name] || permission.name }}</strong><small>{{ permission.reason }}</small></span></div>
                  </div>
                  <el-alert v-if="importSummary.signing_status === 'unsigned'" title="此包没有可验证的发布者签名" type="warning" :closable="false" show-icon />
                  <el-checkbox v-if="importSummary.signing_status === 'unsigned'" v-model="importUnsignedConsent" class="risk-consent">我已确认来源并接受未签名包风险</el-checkbox>
                  <div class="local-install-actions">
                    <span>{{ importStage }}</span>
                    <el-button
                      type="primary"
                      :icon="UploadFilled"
                      :loading="actionBusy"
                      :disabled="importSummary.compatibility_issues.length || (importSummary.signing_status === 'unsigned' && !importUnsignedConsent)"
                      @click="confirmImport"
                    >安装本地包</el-button>
                  </div>
                </div>
              </div>
            </el-tab-pane>

            <el-tab-pane label="已安装" name="installed">
              <div v-if="installed.length" class="plugin-grid installed-grid">
                <article v-for="plugin in installed" :key="plugin.id" class="plugin-card installed-card">
                  <div class="card-heading">
                    <span class="plugin-icon"><component :is="iconFor(plugin)" /></span>
                    <div><h2>{{ plugin.name }}</h2><p>{{ plugin.author.name }} · v{{ plugin.version }}</p></div>
                    <span class="state" :class="plugin.enabled ? 'open' : 'disabled'">{{ plugin.enabled ? '已启用' : '已禁用' }}</span>
                  </div>
                  <p class="description">{{ plugin.description }}</p>
                  <div class="metadata">
                    <span>{{ plugin.webui ? 'WebUI' : 'CLI' }}</span>
                    <span>{{ commandNames(plugin).join(' · ') || '无命令入口' }}</span>
                    <span>{{ plugin.signing_status === 'unsigned' ? '未签名' : '签名已验证' }}</span>
                  </div>
                  <div class="card-actions">
                    <el-button @click="showDetail(plugin)">详情</el-button>
                    <el-button v-if="plugin.webui && plugin.enabled" :icon="Platform" @click="go(plugin.id)">打开</el-button>
                    <el-button :icon="Operation" @click="openManage(plugin)">管理</el-button>
                    <el-dropdown trigger="click">
                      <el-button :icon="MoreFilled" circle aria-label="更多插件操作" />
                      <template #dropdown>
                        <el-dropdown-menu>
                          <el-dropdown-item :icon="SwitchButton" @click="togglePlugin(plugin)">{{ plugin.enabled ? '禁用' : '启用' }}</el-dropdown-item>
                          <el-dropdown-item :icon="Delete" divided @click="confirmUninstall(plugin)">卸载</el-dropdown-item>
                        </el-dropdown-menu>
                      </template>
                    </el-dropdown>
                  </div>
                </article>
              </div>
              <el-empty v-else description="当前没有已安装插件" />
            </el-tab-pane>
          </el-tabs>
        </section>

        <section v-else-if="currentView === 'settings'" class="content-scroll settings-view">
          <div class="page-header"><div><h1>设置</h1><p>Env WebUI 本机偏好</p></div></div>
          <div class="settings-row">
            <div><strong>界面主题</strong><span>应用到宿主和已打开的插件页面</span></div>
            <el-segmented v-model="theme" :options="[{ label: '浅色', value: 'light' }, { label: '深色', value: 'dark' }]" />
          </div>
          <div class="settings-row">
            <div><strong>本机服务</strong><span>启动令牌、会话与写请求保护已启用</span></div>
            <span class="healthy"><CircleCheck />已保护</span>
          </div>
        </section>

        <section v-else class="plugin-content">
          <template v-if="activePlugin">
            <div v-if="activePlugin.missing_required_permissions.length" class="boundary-state">
              <WarningFilled /><h1>需要恢复权限</h1><p>{{ activePlugin.name }} 缺少运行所需的必需权限。</p>
          <div><el-button @click="go('plugins'); pluginTab = 'installed'">返回插件中心</el-button><el-button type="primary" :icon="Lock" @click="openManage(activePlugin)">管理权限</el-button></div>
            </div>
            <div v-else-if="iframeState === 'checking'" class="boundary-state compact-state">
              <el-icon class="is-loading"><Refresh /></el-icon><p>检查插件状态</p>
            </div>
            <div v-else-if="iframeState === 'timeout' || iframeState === 'error'" class="boundary-state">
              <WarningFilled /><h1>插件页面未能加载</h1><p>{{ activePlugin.name }} 的故障未影响 Env WebUI 和其他插件。</p>
              <div><el-button @click="go('plugins'); pluginTab = 'installed'">返回插件中心</el-button><el-button :icon="Refresh" type="primary" @click="go(activePlugin.id)">重新加载</el-button></div>
            </div>
            <iframe
              v-else
              ref="iframeElement"
              class="plugin-frame"
              :title="activePlugin.name"
              :src="`${session.plugin_asset_base}${encodeURIComponent(activePlugin.id)}/`"
              sandbox="allow-scripts"
              @load="iframeLoaded"
            ></iframe>
          </template>
        </section>
      </main>
    </div>

    <el-dialog v-model="detailVisible" width="min(680px, calc(100vw - 28px))" :show-close="false" align-center destroy-on-close>
      <template #header>
        <div v-if="detailPlugin" class="dialog-heading">
          <span class="plugin-icon"><component :is="iconFor(detailPlugin)" /></span>
          <div><h2>{{ detailPlugin.name }}</h2><p>{{ detailPlugin.author.name }} · v{{ detailPlugin.version }}</p></div>
          <el-button text circle :icon="Close" aria-label="关闭详情" @click="detailVisible = false" />
        </div>
      </template>
      <template v-if="detailPlugin">
        <p class="dialog-description">{{ detailPlugin.description }}</p>
        <div class="detail-section"><h3>提供的能力</h3>
          <div v-if="detailPlugin.webui" class="capability"><Platform /><span><strong>WebUI 页面</strong><small>{{ detailPlugin.webui.entry }}</small></span></div>
          <div v-for="command in detailPlugin.commands" :key="typeof command === 'string' ? command : command.name" class="capability"><Tools /><span><strong>{{ typeof command === 'string' ? command : command.name }}</strong><small>{{ commandDescription(command) }}</small></span></div>
          <div v-if="!detailPlugin.webui && !detailPlugin.commands.length" class="capability"><InfoFilled /><span><strong>无可用入口</strong></span></div>
        </div>
        <div class="detail-section"><h3>兼容性</h3><div class="capability"><Cpu /><span><strong>{{ detailPlugin.compatibility_issues.length ? '当前环境不兼容' : '当前环境兼容' }}</strong><small>{{ compatibilityText(detailPlugin) }}</small></span></div></div>
        <div class="detail-section"><h3>权限</h3>
          <div v-for="permission in detailPlugin.permissions" :key="permission.name" class="capability"><Lock /><span><strong>{{ permissionLabels[permission.name] || permission.name }}</strong><small>{{ permission.reason }} · {{ permission.required ? '必需' : '可选' }}</small></span></div>
          <div v-if="!detailPlugin.permissions.length" class="capability"><CircleCheck /><span><strong>无需额外权限</strong></span></div>
        </div>
        <el-alert v-if="detailPlugin.signing_status === 'unsigned'" title="发布者身份未验证" type="warning" :closable="false" show-icon />
      </template>
      <template #footer><el-button type="primary" @click="detailVisible = false">关闭</el-button></template>
    </el-dialog>

    <el-dialog v-model="upgradeVisible" width="min(620px, calc(100vw - 28px))" title="从本地包更新" align-center :close-on-click-modal="!actionBusy">
      <div v-if="upgradeTarget" class="upgrade-target">
        <span class="plugin-icon"><component :is="iconFor(upgradeTarget)" /></span>
        <div><strong>{{ upgradeTarget.name }}</strong><span>当前版本 v{{ upgradeTarget.version }}</span></div>
      </div>
      <label class="upload-zone">
        <input type="file" accept=".epack" @change="selectUpgrade">
        <UploadFilled /><strong>{{ upgradeFile?.name || '选择更新 .epack' }}</strong><span>{{ upgradeStage }}</span>
      </label>
      <template v-if="upgradeSummary">
        <div class="import-review"><strong>{{ upgradeSummary.name }} · v{{ upgradeSummary.version }}</strong><span>{{ upgradeSummary.id }}</span><span>{{ compatibilityText(upgradeSummary) }}</span></div>
        <el-alert v-if="upgradeMismatch" title="插件标识与已安装插件不一致" type="error" :closable="false" show-icon />
        <el-alert v-else-if="upgradeSummary.signing_status === 'unsigned'" title="此包没有可验证的发布者签名" type="warning" :closable="false" show-icon />
        <el-checkbox v-if="!upgradeMismatch && upgradeSummary.signing_status === 'unsigned'" v-model="upgradeUnsignedConsent" class="risk-consent">我已确认来源并接受未签名包风险</el-checkbox>
      </template>
      <template #footer><el-button :disabled="actionBusy" @click="upgradeVisible = false">取消</el-button><el-button type="primary" :loading="actionBusy" :disabled="!upgradeSummary || upgradeMismatch || upgradeSummary.compatibility_issues.length || (upgradeSummary.signing_status === 'unsigned' && !upgradeUnsignedConsent)" @click="confirmUpgrade">确认更新</el-button></template>
    </el-dialog>

    <el-dialog v-model="manageVisible" width="min(660px, calc(100vw - 28px))" title="插件管理" align-center>
      <template v-if="managedPlugin">
        <div class="manage-heading"><span class="plugin-icon"><component :is="iconFor(managedPlugin)" /></span><div><strong>{{ managedPlugin.name }}</strong><span>v{{ managedPlugin.version }} · {{ managedPlugin.enabled ? '已启用' : '已禁用' }}</span></div></div>
        <h3 class="manage-section-title">权限</h3>
        <el-checkbox-group v-model="permissionSelection" class="permission-controls">
          <el-checkbox v-for="permission in managedPlugin.permissions" :key="permission.name" :value="permission.name">
            <span><strong>{{ permissionLabels[permission.name] }}</strong><small>{{ permission.reason }} · {{ permission.required ? '必需' : '可选' }}</small></span>
          </el-checkbox>
        </el-checkbox-group>
        <el-empty v-if="!managedPlugin.permissions.length" :image-size="48" description="此插件无需额外权限" />
        <div class="manage-actions"><el-button :loading="actionBusy" :icon="Lock" @click="savePermissions">保存权限</el-button><el-button :loading="actionBusy" :icon="DataAnalysis" @click="runDoctor(managedPlugin)">运行诊断</el-button><el-button :loading="actionBusy" :icon="ArrowUp" @click="beginUpdate(managedPlugin)">从本地包更新</el-button><el-button :icon="Delete" type="danger" plain @click="confirmUninstall(managedPlugin)">卸载</el-button></div>
        <el-alert v-if="diagnostic" :title="diagnostic.status === 'ok' ? '诊断通过' : '诊断发现问题'" :type="diagnostic.status === 'ok' ? 'success' : 'error'" :description="diagnostic.plugins.flatMap((item) => item.issues).join('；') || '状态、入口和资源均一致'" :closable="false" show-icon />
      </template>
    </el-dialog>

    <el-dialog v-model="uninstallVisible" width="min(520px, calc(100vw - 28px))" title="卸载插件" align-center append-to-body>
      <p>卸载 {{ managedPlugin?.name }} 后，其命令和 WebUI 入口将立即移除。</p>
      <el-radio-group v-model="purgeData" class="uninstall-options">
        <el-radio :value="false"><span><strong>保留插件数据</strong><small>重新安装后可继续使用</small></span></el-radio>
        <el-radio :value="true"><span><strong>删除插件数据</strong><small>配置、数据和缓存将永久删除</small></span></el-radio>
      </el-radio-group>
      <template #footer><el-button :disabled="actionBusy" @click="uninstallVisible = false">取消</el-button><el-button type="danger" :loading="actionBusy" @click="uninstallPlugin">确认卸载</el-button></template>
    </el-dialog>
  </el-config-provider>
</template>
