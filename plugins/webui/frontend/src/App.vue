<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import {
  ArrowUp,
  Box,
  CircleCheck,
  Close,
  Cpu,
  DataAnalysis,
  Delete,
  Expand,
  Fold,
  Grid,
  InfoFilled,
  Lock,
  Menu,
  MoreFilled,
  Operation,
  Plus,
  Platform,
  Refresh,
  FolderOpened,
  Setting,
  SwitchButton,
  Tools,
  Search,
  UploadFilled,
  WarningFilled,
} from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api, setCsrfToken } from './api'
import {
  permissionLabels,
  stageLabels,
} from './constants'
import {
  explainMarketError,
  formatBytes,
  formatSpeed,
  reasonText,
  requestedPluginId,
  runtimeText,
  sdkActionLabel,
  sdkHasDownloadProgress,
  sdkStateLabel,
  sdkTaskIsIndeterminate,
  sdkTaskOperationStatusLabel,
  sdkTaskOperationType,
  sdkTaskStageLabel,
  sdkTaskTitle,
  syncViewUrl,
} from './utils/formatters'
import {
  blockingReasons,
  canInstallFromMarket,
  canUninstallFromMarket,
  canUpgradeFromMarket,
  capabilityLabel,
  commandDescription,
  commandNames,
  compatibilityText,
  diagnosisArtifacts,
  diagnosisOf,
  diagnosisReasons,
  hostBackendContext,
  iconFor,
  installedPluginFor as findInstalledPlugin,
  marketActionLabel,
  marketStateClass,
  marketStateLabel,
} from './utils/plugins'
import type {
  ContextMenuSnapshot,
  DoctorResult,
  EnvPlugin,
  MarketCatalog,
  MarketPrepareError,
  MarketStatus,
  PluginHostBackendContext,
  PluginHostContext,
  Session,
  ToolchainForm,
  ToolchainSnapshot,
  UploadSummary,
} from './types/api'
import { useSdk } from './composables/useSdk'
import envLogo from '@env-brand/env.png'

const session = ref<Session | null>(null)
const installed = ref<EnvPlugin[]>([])
const loading = ref(true)
const actionBusy = ref(false)
const sidebarOpen = ref(false)
const sidebarCollapsed = ref(localStorage.getItem('env-sidebar-collapsed') === 'true')
const currentView = ref('plugins')
const closing = ref(false)
const pluginTab = ref('installed')
const settingsTab = ref('general')
const theme = ref<'light' | 'dark'>((localStorage.getItem('env-theme') as 'light' | 'dark') || 'light')
const detailVisible = ref(false)
const detailPlugin = ref<EnvPlugin | null>(null)
const marketQuery = ref('')
const marketSort = ref('updated')
const marketCatalog = ref<MarketCatalog>({ items: [], total: 0 })
const marketLoading = ref(false)
const marketError = ref('')
const marketStatus = ref<MarketStatus | null>(null)
const marketDetail = ref<EnvPlugin | null>(null)
const marketDetailVisible = ref(false)
const marketPrepare = ref<UploadSummary | null>(null)
const marketPrepareVisible = ref(false)
const marketUnsignedConsent = ref(false)
const marketPrepareStage = ref('准备在线插件包')
const marketPrepareError = ref<MarketPrepareError | null>(null)
const importFile = ref<File | null>(null)
const importSummary = ref<UploadSummary | null>(null)
const importUnsignedConsent = ref(false)
const importStage = ref('选择本地包')
const upgradeVisible = ref(false)
const upgradeTarget = ref<EnvPlugin | null>(null)
const upgradeFile = ref<File | null>(null)
const upgradeSummary = ref<UploadSummary | null>(null)
const upgradeUnsignedConsent = ref(false)
const upgradeStage = ref('选择本地包')
const manageVisible = ref(false)
const managedPlugin = ref<EnvPlugin | null>(null)
const permissionSelection = ref<string[]>([])
const diagnostic = ref<DoctorResult | null>(null)
const uninstallVisible = ref(false)
const purgeData = ref(false)
const toolchainState = ref<ToolchainSnapshot | null>(null)
const toolchainLoading = ref(false)
const toolchainBusy = ref(false)
const toolchainEditorVisible = ref(false)
const toolchainEditingName = ref<string | null>(null)
const toolchainForm = ref<ToolchainForm>({ name: '', path: '', description: '' })
const toolchainError = ref('')
const contextMenuState = ref<ContextMenuSnapshot | null>(null)
const contextMenuBusy = ref(false)
type IframeState = 'idle' | 'checking' | 'loading' | 'ready' | 'timeout' | 'error'
const iframeState = ref<IframeState>('idle')
const iframeStates = ref<Record<string, IframeState>>({})
const mountedKeepAlivePluginIds = ref(new Set<string>())
const iframeElements = new Map<string, HTMLIFrameElement>()
const iframeTimers = new Map<string, number>()
const iframeCheckGenerations = new Map<string, number>()

const {
  sdkState,
  sdkSelection,
  sdkLoading,
  sdkBusy,
  sdkCancelBusy,
  sdkError,
  sdkPlanResult,
  sdkTaskState,
  sdkDirty,
  loadSdk,
  setSdkEnabled,
  setSdkVersion,
  sdkOperationText,
  previewSdkPlan,
  applySdkPlan,
  cancelSdkTask,
} = useSdk()

function installedPluginFor(plugin?: Partial<EnvPlugin> | null): EnvPlugin | undefined {
  return findInstalledPlugin(installed.value, plugin)
}

const marketEnabled = computed(() => Boolean(session.value?.market?.enabled))
const navigablePlugins = computed(() => installed.value.filter((item) => item.enabled && item.webui))
const activePlugin = computed(() => installed.value.find((item) => item.id === currentView.value))
const mountedFramePlugins = computed(() => navigablePlugins.value.filter((plugin) => {
  if (plugin.missing_required_permissions?.length) return false
  const state = iframeStates.value[plugin.id] || 'idle'
  if (plugin.webui?.keep_alive) {
    return mountedKeepAlivePluginIds.value.has(plugin.id) && ['loading', 'ready'].includes(state)
  }
  return plugin.id === activePlugin.value?.id && ['loading', 'ready'].includes(state)
}))
const upgradeMismatch = computed(() => (
  upgradeSummary.value && upgradeTarget.value && upgradeSummary.value.id !== upgradeTarget.value.id
))
const marketSourceLabel = computed(() => {
  if (!marketEnabled.value) return '未配置'
  return session.value.market.source === 'env' ? '环境变量' : '配置文件'
})

function toggleSidebarCollapsed() {
  sidebarCollapsed.value = !sidebarCollapsed.value
  localStorage.setItem('env-sidebar-collapsed', String(sidebarCollapsed.value))
}

function closeBrowserWindow() {
  try {
    // Browsers only allow window.close() for script-opened windows. Opening the
    // current browsing context first enables that path where supported.
    window.open('', '_self')
    window.close()
  } catch {
    // Fall through to the blank-page fallback below.
  }
  window.setTimeout(() => {
    if (window.closed) return
    try {
      window.location.replace('about:blank')
    } catch {
      // The browser may have closed the context between the checks.
    }
  }, 150)
}

async function confirmCloseWebUI() {
  if (closing.value) return
  try {
    await ElMessageBox.confirm(
      '关闭后 Env WebUI 服务将退出，当前页面也会关闭。是否继续？',
      '关闭 WebUI',
      {
        type: 'warning',
        confirmButtonText: '关闭并退出',
        cancelButtonText: '取消',
        closeOnClickModal: false,
      },
    )
  } catch {
    return
  }
  closing.value = true
  try {
    await api.shutdown()
    closeBrowserWindow()
  } catch (error) {
    closing.value = false
    ElMessage.error(`关闭 WebUI 失败：${error.message}`)
  }
}

function mergeCatalogItem(detail) {
  const items = marketCatalog.value.items || []
  const index = items.findIndex((item) => item.id === detail.id)
  if (index < 0) return
  const next = items.slice()
  next[index] = {
    ...next[index],
    action: detail.action,
    compatible: detail.compatible,
    diagnosis: detail.diagnosis,
    compatibility_message: detail.compatibility_message,
  }
  marketCatalog.value = { ...marketCatalog.value, items: next }
}

async function bootstrap() {
  loading.value = true
  try {
    await reloadAll()
  } catch (error) {
    ElMessage.error(error.message)
  } finally {
    loading.value = false
  }
}

async function reloadAll() {
  const nextSession = await api.session()
  session.value = nextSession
  setCsrfToken(nextSession.csrf_token)
  const installedItems = await api.plugins()
  const previousPlugins = new Map(installed.value.map((item) => [item.id, item]))
  installed.value = installedItems
  const nextPlugins = new Map(installedItems.map((item) => [item.id, item]))
  let activeFrameDiscarded = false
  for (const [pluginId] of Object.entries(iframeStates.value)) {
    const previous = previousPlugins.get(pluginId)
    const next = nextPlugins.get(pluginId)
    if (!next || !next.enabled || !next.webui || (
      previous && (
        previous.version !== next.version
        || Boolean(previous.webui?.keep_alive) !== Boolean(next.webui?.keep_alive)
        || previous.webui?.entry !== next.webui?.entry
      )
    )) {
      if (currentView.value === pluginId) activeFrameDiscarded = true
      discardPluginFrame(pluginId)
    }
  }
  mountedKeepAlivePluginIds.value = new Set(
    [...mountedKeepAlivePluginIds.value].filter((pluginId) => nextPlugins.get(pluginId)?.webui?.keep_alive),
  )
  if (currentView.value === 'plugins') {
    const requested = installedItems.find((item) => item.id === requestedPluginId())
    if (requested?.enabled && requested.webui) go(requested.id)
    else if (requestedPluginId()) syncViewUrl('plugins')
  }
  if (currentView.value !== 'plugins' && currentView.value !== 'settings') {
    const current = installedItems.find((item) => item.id === currentView.value)
    if (!current?.enabled || !current.webui) {
      currentView.value = 'plugins'
      syncViewUrl('plugins')
    } else if (activeFrameDiscarded) {
      go(current.id)
    }
  }
  await loadSdk()
  await Promise.all([loadToolchains(), loadContextMenu()])
  if (marketEnabled.value && pluginTab.value === 'online') await loadMarket()
}

async function loadToolchains() {
  toolchainLoading.value = true
  toolchainError.value = ''
  try {
    toolchainState.value = await api.toolchains()
  } catch (error) {
    toolchainError.value = error.message
  } finally {
    toolchainLoading.value = false
  }
}

async function saveToolchain() {
  if (toolchainBusy.value) return
  const editing = Boolean(toolchainEditingName.value)
  toolchainBusy.value = true
  try {
    toolchainState.value = toolchainEditingName.value
      ? await api.updateToolchain(toolchainEditingName.value, { ...toolchainForm.value })
      : await api.addToolchain({ ...toolchainForm.value })
    toolchainEditorVisible.value = false
    toolchainEditingName.value = null
    toolchainForm.value = { name: '', path: '', description: '' }
    ElMessage.success(editing ? '本地工具链已更新' : '本地工具链已添加')
  } catch (error) {
    ElMessage.error(error.message)
  } finally {
    toolchainBusy.value = false
  }
}

function openToolchainEditor(entry = null) {
  toolchainEditingName.value = entry?.name || null
  toolchainForm.value = entry
    ? { name: entry.name, path: entry.path, description: entry.description || '' }
    : { name: '', path: '', description: '' }
  toolchainEditorVisible.value = true
}

function closeToolchainEditor() {
  if (toolchainBusy.value) return
  toolchainEditorVisible.value = false
  toolchainEditingName.value = null
  toolchainForm.value = { name: '', path: '', description: '' }
}

function resetToolchainEditor() {
  toolchainEditingName.value = null
  toolchainForm.value = { name: '', path: '', description: '' }
}

async function removeToolchain(entry) {
  if (toolchainBusy.value) return
  try {
    await ElMessageBox.confirm(
      `将从 sdk_cfg.json 中删除“${entry.name}”，不会删除工具链目录，是否继续？`,
      '确认删除工具链配置',
      { type: 'warning', confirmButtonText: '确认删除', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  toolchainBusy.value = true
  try {
    toolchainState.value = await api.removeToolchain(entry.name)
    ElMessage.success('工具链配置已删除')
  } catch (error) {
    ElMessage.error(error.message)
  } finally {
    toolchainBusy.value = false
  }
}

function addDetectedToolchain(item) {
  openToolchainEditor()
  toolchainForm.value = {
    name: item.config_name || '',
    path: item.path || '',
    description: item.name || '',
  }
}

async function loadContextMenu() {
  try {
    contextMenuState.value = await api.fileContextMenu()
  } catch (error) {
    contextMenuState.value = { available: false, supported: false, error: error.message }
  }
}

async function setContextMenu(enabled) {
  if (contextMenuBusy.value || !contextMenuState.value?.supported) return
  if (!enabled) {
    try {
      await ElMessageBox.confirm(
        '将移除“Env终端中打开...”菜单，不会删除 Env 或工具链文件，是否继续？',
        '确认移除文件资源管理器菜单',
        { type: 'warning', confirmButtonText: '确认移除', cancelButtonText: '取消' },
      )
    } catch {
      return
    }
  }
  contextMenuBusy.value = true
  try {
    contextMenuState.value = enabled
      ? await api.installFileContextMenu()
      : await api.removeFileContextMenu()
    ElMessage.success(enabled ? '文件资源管理器菜单已添加' : '文件资源管理器菜单已移除')
  } catch (error) {
    ElMessage.error(error.message)
  } finally {
    contextMenuBusy.value = false
  }
}

async function loadMarket() {
  if (!marketEnabled.value) return
  marketLoading.value = true
  marketError.value = ''
  try {
    const [status, catalog] = await Promise.all([
      api.marketStatus(),
      api.marketPlugins({
        q: marketQuery.value.trim(),
        sort: marketSort.value,
        page: 1,
        pageSize: 50,
      }),
    ])
    marketStatus.value = status
    marketCatalog.value = catalog
    if (!status.reachable) marketError.value = status.message || '插件市场不可达'
  } catch (error) {
    marketCatalog.value = { items: [], total: 0 }
    marketError.value = error.message
  } finally {
    marketLoading.value = false
  }
}

watch(theme, (value) => {
  document.documentElement.dataset.theme = value
  localStorage.setItem('env-theme', value)
  sendPluginContexts()
}, { immediate: true })

watch(pluginTab, (value) => {
  if (value === 'online' && marketEnabled.value) loadMarket()
})

function clearIframeTimer(pluginId: string) {
  const timer = iframeTimers.get(pluginId)
  if (timer !== undefined) {
    window.clearTimeout(timer)
    iframeTimers.delete(pluginId)
  }
}

function nextIframeCheckGeneration(pluginId: string) {
  const generation = (iframeCheckGenerations.get(pluginId) || 0) + 1
  iframeCheckGenerations.set(pluginId, generation)
  return generation
}

function isCurrentIframeCheck(pluginId: string, generation: number) {
  return iframeCheckGenerations.get(pluginId) === generation
}

function discardPluginFrame(pluginId: string) {
  nextIframeCheckGeneration(pluginId)
  clearIframeTimer(pluginId)
  const nextStates = { ...iframeStates.value }
  delete nextStates[pluginId]
  iframeStates.value = nextStates
  mountedKeepAlivePluginIds.value = new Set(
    [...mountedKeepAlivePluginIds.value].filter((id) => id !== pluginId),
  )
  if (currentView.value === pluginId) iframeState.value = 'idle'
}

function setIframeState(pluginId: string, state: IframeState) {
  iframeStates.value = { ...iframeStates.value, [pluginId]: state }
  if (currentView.value === pluginId) iframeState.value = state
}

function setIframeElement(pluginId: string, element: unknown) {
  if (element instanceof HTMLIFrameElement) iframeElements.set(pluginId, element)
  else iframeElements.delete(pluginId)
}

function startPluginCheck(view: string) {
  const generation = nextIframeCheckGeneration(view)
  clearIframeTimer(view)
  setIframeState(view, 'checking')
  api.doctor(view).then((result) => {
    if (!isCurrentIframeCheck(view, generation)) return
    if (result.status !== 'ok') {
      setIframeState(view, 'error')
      return
    }
    setIframeState(view, 'loading')
    clearIframeTimer(view)
    const timer = window.setTimeout(() => {
      if (!isCurrentIframeCheck(view, generation)) return
      if ((iframeStates.value[view] || 'idle') === 'loading') setIframeState(view, 'timeout')
      iframeTimers.delete(view)
    }, 8000)
    iframeTimers.set(view, timer)
  }).catch(() => {
    if (!isCurrentIframeCheck(view, generation)) return
    clearIframeTimer(view)
    setIframeState(view, 'error')
  })
}

function go(view: string, forceReload = false) {
  currentView.value = view
  sidebarOpen.value = false
  syncViewUrl(view)
  if (view === 'plugins' || view === 'settings') {
    iframeState.value = 'idle'
    return
  }
  const plugin = installed.value.find((item) => item.id === view)
  if (!plugin?.webui) {
    iframeState.value = 'idle'
    return
  }
  if (plugin.webui.keep_alive) {
    mountedKeepAlivePluginIds.value = new Set([...mountedKeepAlivePluginIds.value, view])
    if (!forceReload && iframeStates.value[view] === 'ready') {
      iframeState.value = 'ready'
      nextTick(() => sendPluginContext(view))
      return
    }
  }
  startPluginCheck(view)
}

function showDetail(plugin) {
  detailPlugin.value = plugin
  detailVisible.value = true
}

async function showMarketDetail(plugin) {
  actionBusy.value = true
  try {
    marketDetail.value = await api.marketPlugin(plugin.id)
    mergeCatalogItem(marketDetail.value)
    marketDetailVisible.value = true
  } catch (error) {
    ElMessage.error(error.message)
  } finally {
    actionBusy.value = false
  }
}

async function beginMarketInstall(plugin) {
  if (!plugin || (!canInstallFromMarket(plugin) && !canUpgradeFromMarket(plugin))) return
  marketPrepare.value = null
  marketPrepareError.value = null
  marketUnsignedConsent.value = false
  marketPrepareStage.value = '解析兼容制品并下载'
  marketPrepareVisible.value = true
  actionBusy.value = true
  try {
    marketPrepare.value = await api.prepareMarketPlugin(plugin.id)
    marketPrepareStage.value = '检查通过，等待确认'
  } catch (error) {
    marketPrepareStage.value = '准备失败'
    marketPrepareError.value = {
      stage: error.details?.stage || 'resolve',
      code: error.code,
      message: error.message,
      details: error.details,
      diagnosis: error.details?.diagnosis,
    }
    if (error.details?.diagnosis) {
      mergeCatalogItem({
        id: plugin.id,
        action: error.code === 'yanked' || error.code === 'incompatible' ? 'incompatible' : plugin.action,
        compatible: false,
        diagnosis: error.details.diagnosis,
        compatibility_message: error.details.diagnosis.summary,
      })
    }
  } finally {
    actionBusy.value = false
  }
}

function confirmMarketUninstall(plugin) {
  const local = installedPluginFor(plugin)
  if (!local) return
  confirmUninstall(local)
}

async function confirmMarketInstall() {
  if (!marketPrepare.value) return
  if (marketPrepare.value.signing_status === 'unsigned' && !marketUnsignedConsent.value) return
  const installedPlugin = installed.value.find((item) => item.id === marketPrepare.value.id)
  actionBusy.value = true
  marketPrepareStage.value = installedPlugin ? '安装新版本并切换状态' : '安装后端并注册前端资源'
  try {
    const result = installedPlugin
      ? await api.upgradeUpload(marketPrepare.value.id, marketPrepare.value.upload_id, marketUnsignedConsent.value)
      : await api.installUpload(marketPrepare.value.upload_id, marketUnsignedConsent.value)
    marketPrepareStage.value = '状态已提交到 Env Core'
    await reloadAll()
    marketPrepareVisible.value = false
    marketDetailVisible.value = false
    ElMessage.success(installedPlugin ? `${result.name} 已更新到 v${result.version}` : `${result.name} 已安装`)
  } catch (error) {
    marketPrepareStage.value = '安装失败，请重新准备插件包'
    marketPrepareError.value = {
      stage: 'install',
      code: error.code,
      message: error.message,
      details: error.details,
    }
    marketPrepare.value = null
  } finally {
    actionBusy.value = false
  }
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
    if (marketDetail.value?.id === managedPlugin.value.id) marketDetailVisible.value = false
    await reloadAll()
    ElMessage.success(`${name} 已卸载`)
  } catch (error) {
    ElMessage.error(error.message)
  } finally {
    actionBusy.value = false
  }
}

function sendPluginContext(pluginId = activePlugin.value?.id) {
  if (!pluginId) return
  const frame = iframeElements.get(pluginId)
  const plugin = installed.value.find((item) => item.id === pluginId)
  if (!frame?.contentWindow || !plugin) return
  const asset = session.value?.plugin_assets?.[pluginId]
  const backend: PluginHostBackendContext | null = hostBackendContext(asset)
  const payload: PluginHostContext = {
    protocolVersion: 1,
    pluginId,
    sdkVersion: session.value?.frontend_sdk || '1.0.0',
    theme: theme.value,
    language: 'zh-CN',
    backend,
    features: backend ? ['backend.http', 'backend.websocket'] : [],
  }
  frame.contentWindow.postMessage({
    type: 'env.host.context',
    payload,
  }, '*')
}

function sendPluginContexts() {
  iframeElements.forEach((_frame, pluginId) => sendPluginContext(pluginId))
}

function iframeLoaded(pluginId: string) {
  setIframeState(pluginId, 'ready')
  clearIframeTimer(pluginId)
  nextTick(() => sendPluginContext(pluginId))
}

function receivePluginMessage(event) {
  const frameEntry = [...iframeElements.entries()].find(([, frame]) => event.source === frame.contentWindow)
  if (!frameEntry) return
  const [pluginId] = frameEntry
  if (event.data?.type === 'env.host.ready') {
    setIframeState(pluginId, 'ready')
    clearIframeTimer(pluginId)
    sendPluginContext(pluginId)
  } else if (event.data?.type === 'env.host.error') {
    setIframeState(pluginId, 'error')
  }
}

onMounted(() => {
  window.addEventListener('message', receivePluginMessage)
  bootstrap()
})

onBeforeUnmount(() => {
  window.removeEventListener('message', receivePluginMessage)
  iframeTimers.forEach((timer) => window.clearTimeout(timer))
  iframeTimers.clear()
})
</script>

<template>
  <el-config-provider>
    <div class="app-shell" :class="{ 'sidebar-open': sidebarOpen, 'sidebar-collapsed': sidebarCollapsed }" v-loading="loading">
      <aside id="env-sidebar" class="sidebar">
        <div class="brand">
          <img class="brand-logo" :src="envLogo" alt="RT-Thread Env" />
          <el-tooltip :content="sidebarCollapsed ? '展开侧边栏' : '折叠侧边栏'">
            <el-button
              class="sidebar-toggle"
              text
              circle
              :icon="sidebarCollapsed ? Expand : Fold"
              :aria-label="sidebarCollapsed ? '展开侧边栏' : '折叠侧边栏'"
              :aria-expanded="!sidebarCollapsed"
              aria-controls="env-sidebar"
              @click="toggleSidebarCollapsed"
            />
          </el-tooltip>
          <el-button class="mobile-close" text circle :icon="Close" aria-label="关闭导航" @click="sidebarOpen = false" />
        </div>

        <nav class="plugin-navigation" aria-label="已安装插件">
          <div class="nav-heading"><span>已安装插件</span><b>{{ navigablePlugins.length }}</b></div>
          <button
            v-for="plugin in navigablePlugins"
            :key="plugin.id"
            class="nav-entry"
            :class="{ active: currentView === plugin.id }"
            :title="sidebarCollapsed ? plugin.name : undefined"
            @click="go(plugin.id)"
          >
            <span class="nav-icon"><component :is="iconFor(plugin)" /></span>
            <span>{{ plugin.name }}</span>
            <i v-if="plugin.missing_required_permissions.length" class="nav-warning" title="需要恢复权限"></i>
          </button>
          <div v-if="!navigablePlugins.length" class="nav-empty">尚无可打开的插件</div>
        </nav>

        <div class="sidebar-footer">
          <button class="nav-entry footer-entry" :class="{ active: currentView === 'plugins' }" aria-label="插件中心" @click="go('plugins')">
            <span class="nav-icon"><Grid /></span><span>插件中心</span>
          </button>
          <button class="nav-entry" :class="{ active: currentView === 'settings' }" aria-label="设置" @click="go('settings')">
            <span class="nav-icon"><Setting /></span><span>设置</span>
          </button>
          <button
            class="nav-entry exit-entry"
            :class="{ 'is-busy': closing }"
            aria-label="退出 WebUI"
            :aria-busy="closing"
            :disabled="closing"
            @click="confirmCloseWebUI"
          >
            <span class="nav-icon"><SwitchButton /></span><span>退出 WebUI</span>
          </button>
        </div>
      </aside>

      <button class="mobile-scrim" aria-label="关闭导航" @click="sidebarOpen = false"></button>

      <main class="main-shell">
        <el-tooltip content="打开导航">
          <el-button class="mobile-menu" text circle :icon="Menu" aria-label="打开导航" @click="sidebarOpen = true" />
        </el-tooltip>

        <section v-if="currentView === 'plugins'" class="content-scroll plugin-center-view">
          <div class="page-header">
            <div>
              <h1>插件中心</h1>
              <p>{{ marketEnabled ? '浏览在线插件，或从本机安装和管理 Env 插件' : '从本机安装和管理 Env 插件' }}</p>
            </div>
            <div class="page-actions">
              <el-tooltip content="刷新插件状态"><el-button :icon="Refresh" circle aria-label="刷新插件状态" @click="reloadAll" /></el-tooltip>
            </div>
          </div>

          <el-tabs v-model="pluginTab" class="plugin-tabs">
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

            <el-tab-pane v-if="marketEnabled" label="在线插件" name="online">
              <div class="market-toolbar">
                <el-input
                  v-model="marketQuery"
                  clearable
                  placeholder="搜索插件 id 或名称"
                  :prefix-icon="Search"
                  @keyup.enter="loadMarket"
                  @clear="loadMarket"
                />
                <el-select v-model="marketSort" style="width: 160px" @change="loadMarket">
                  <el-option label="最近更新" value="updated" />
                  <el-option label="下载次数" value="downloads" />
                  <el-option label="名称" value="name" />
                </el-select>
                <el-button :icon="Refresh" :loading="marketLoading" @click="loadMarket">刷新目录</el-button>
              </div>
              <el-alert
                v-if="marketError"
                :title="marketError"
                type="warning"
                :closable="false"
                show-icon
                class="market-alert"
              />
              <div v-else-if="marketCatalog.items.length" class="plugin-grid market-grid" v-loading="marketLoading">
                <article v-for="plugin in marketCatalog.items" :key="plugin.id" class="plugin-card market-card">
                  <div class="card-heading">
                    <span class="plugin-icon"><component :is="iconFor(plugin)" /></span>
                    <div>
                      <h2>{{ plugin.name }}</h2>
                      <p>{{ plugin.id }} · v{{ plugin.latest_version }}</p>
                    </div>
                    <span class="state" :class="marketStateClass(plugin)">{{ marketStateLabel(plugin) }}</span>
                  </div>
                  <p class="description">{{ plugin.description }}</p>
                  <div class="metadata">
                    <span v-for="capability in plugin.capabilities || []" :key="capability">{{ capabilityLabel(capability) }}</span>
                    <span>下载 {{ plugin.download_count || 0 }}</span>
                    <span v-if="plugin.installed">本机 v{{ plugin.installed_version }}</span>
                  </div>
                  <p v-if="plugin.action === 'incompatible'" class="market-hint">
                    {{ reasonText(diagnosisReasons(plugin)[0]) || plugin.compatibility_message || '打开详情可查看不能安装的原因' }}
                  </p>
                  <div class="card-actions">
                    <el-button @click="showMarketDetail(plugin)">详情</el-button>
                    <el-button
                      v-if="canInstallFromMarket(plugin) || canUpgradeFromMarket(plugin)"
                      type="primary"
                      :loading="actionBusy"
                      @click="beginMarketInstall(plugin)"
                    >{{ marketActionLabel(plugin) }}</el-button>
                    <el-button
                      v-else-if="plugin.action === 'incompatible' && !plugin.installed"
                      disabled
                    >{{ marketActionLabel(plugin) }}</el-button>
                    <el-button
                      v-if="canUninstallFromMarket(plugin)"
                      :icon="Delete"
                      type="danger"
                      plain
                      :loading="actionBusy"
                      @click="confirmMarketUninstall(plugin)"
                    >卸载</el-button>
                  </div>
                </article>
              </div>
              <el-empty
                v-else
                :description="marketQuery.trim() ? '没有匹配的在线插件' : '目录为空'"
              />
            </el-tab-pane>

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

          </el-tabs>
        </section>

        <section v-else-if="currentView === 'settings'" class="content-scroll settings-view">
          <div class="page-header"><div><h1>设置</h1><p>Env WebUI 本机偏好</p></div></div>
          <el-tabs v-model="settingsTab" class="settings-tabs">
            <el-tab-pane label="常规" name="general">
              <div class="settings-row">
                <div><strong>界面主题</strong><span>应用到宿主和已打开的插件页面</span></div>
                <el-segmented v-model="theme" :options="[{ label: '浅色', value: 'light' }, { label: '深色', value: 'dark' }]" />
              </div>
              <div class="settings-row">
                <div><strong>本机服务</strong><span>启动令牌、会话与写请求保护已启用</span></div>
                <span class="healthy"><CircleCheck />已保护</span>
              </div>
              <div class="settings-row">
                <div>
                  <strong>在线插件市场</strong>
                  <span>{{ marketEnabled ? `${session.market.url} · ${marketSourceLabel}` : '未配置时不显示在线插件页面' }}</span>
                </div>
                <span :class="marketEnabled ? 'healthy' : 'muted-status'">{{ marketEnabled ? '已启用' : '未配置' }}</span>
              </div>
              <div v-if="contextMenuState?.platform === 'Windows'" class="settings-row context-menu-setting">
                <div>
                  <strong>文件资源管理器右键菜单</strong>
                  <span>在目录和目录空白区域增加“Env终端中打开...”</span>
                </div>
                <div class="context-menu-control">
                  <span :class="contextMenuState?.installed ? 'healthy' : 'muted-status'">
                    {{ contextMenuState?.installed ? '已添加' : contextMenuState?.supported ? '未添加' : '当前平台不支持' }}
                  </span>
                  <el-switch
                    :model-value="Boolean(contextMenuState?.installed)"
                    :loading="contextMenuBusy"
                    :disabled="!contextMenuState?.supported || contextMenuBusy"
                    @update:model-value="setContextMenu"
                  />
                </div>
              </div>
            </el-tab-pane>
            <el-tab-pane label="本地工具链配置" name="toolchains">
              <div class="toolchain-toolbar">
                <div>
                  <strong>本地工具链</strong>
                  <span v-if="toolchainState">{{ toolchainState.platform }} · {{ toolchainState.config_path }}</span>
                  <span v-else>读取 sdk_cfg.json</span>
                  <span class="toolchain-toolbar-note">Env 会优先使用名称匹配的工具链。</span>
                </div>
                <div class="toolchain-toolbar-actions">
                  <el-button :icon="Refresh" :loading="toolchainLoading" :disabled="toolchainBusy" @click="loadToolchains">刷新</el-button>
                  <el-button class="sdk-primary-action sdk-action-button" type="primary" :icon="Plus" :disabled="toolchainBusy" @click="openToolchainEditor()">添加工具链</el-button>
                </div>
              </div>
              <el-alert v-if="toolchainError" :title="toolchainError" type="error" :closable="false" show-icon />
              <el-skeleton v-else-if="toolchainLoading && !toolchainState" :rows="4" animated />
              <template v-else-if="toolchainState">
                <div class="toolchain-list" v-if="toolchainState.entries?.length">
                  <div class="toolchain-list-header" aria-hidden="true">
                    <span>名称</span><span>路径</span><span>说明</span><span>操作</span>
                  </div>
                  <div v-for="entry in toolchainState.entries" :key="entry.name" class="toolchain-list-row">
                    <strong>{{ entry.name }}</strong>
                    <code>{{ entry.path }}</code>
                    <span>{{ entry.description || '未填写' }}</span>
                    <div class="toolchain-row-actions">
                      <el-button size="small" :icon="Operation" :disabled="toolchainBusy" @click="openToolchainEditor(entry)">编辑</el-button>
                      <el-button type="danger" plain size="small" :icon="Delete" :disabled="toolchainBusy" @click="removeToolchain(entry)">删除</el-button>
                    </div>
                  </div>
                </div>
                <el-empty v-else :image-size="48" description="尚未配置本地工具链" />
                <div v-if="toolchainState.platform === 'Windows'" class="toolchain-detection">
                  <div class="toolchain-detection-heading">
                    <div><strong>Windows 工具链探测</strong><span>Keil MDK 和 IAR Embedded Workbench</span></div>
                    <el-tag type="info" effect="plain">自动探测</el-tag>
                  </div>
                  <div v-if="toolchainState.detected?.length" class="toolchain-detected-list">
                    <div v-for="item in toolchainState.detected" :key="item.id" class="toolchain-detected-row">
                      <span class="toolchain-detected-icon"><FolderOpened /></span>
                      <div><strong>{{ item.name }}</strong><small>{{ item.path }}</small></div>
                      <el-tag v-if="item.configured" type="success" effect="plain">已配置</el-tag>
                      <el-button v-else size="small" :icon="Plus" :disabled="toolchainBusy" @click="addDetectedToolchain(item)">加入配置</el-button>
                    </div>
                  </div>
                  <el-empty v-else :image-size="42" description="未探测到 Keil MDK 或 IAR 工具链" />
                </div>
              </template>
            </el-tab-pane>
            <el-tab-pane label="SDK 管理" name="sdk">
              <div class="sdk-toolbar">
                <div>
                  <strong>主机 SDK</strong>
                  <span v-if="sdkState">{{ sdkState.platform }} · {{ sdkState.index_root }}</span>
                  <span v-else>读取 SDK 索引</span>
                  <span class="sdk-toolbar-note">Env 会根据使用的工具链命令名称，自动从已安装的工具链中探测并使用匹配项。</span>
                </div>
                <div class="sdk-toolbar-actions">
                  <el-button :icon="Refresh" :loading="sdkLoading" :disabled="sdkBusy" @click="loadSdk">刷新</el-button>
                  <el-button class="sdk-primary-action sdk-action-button" type="primary" :loading="sdkBusy" :disabled="!sdkState || !sdkDirty" @click="previewSdkPlan">预览变更</el-button>
                </div>
              </div>
              <div v-if="sdkTaskState" class="sdk-task-status">
                <div class="sdk-task-heading">
                  <div class="sdk-task-title">
                    <el-icon v-if="sdkTaskState.status === 'queued' || sdkTaskState.status === 'running'" class="is-loading"><Refresh /></el-icon>
                    <strong>{{ sdkTaskTitle(sdkTaskState) }}</strong>
                    <span v-if="sdkTaskState.operation_total">操作 {{ sdkTaskState.operation_index || 0 }} / {{ sdkTaskState.operation_total }}</span>
                  </div>
                  <div class="sdk-task-heading-actions">
                    <span class="sdk-task-stage">{{ sdkTaskStageLabel(sdkTaskState.stage) }}</span>
                    <el-button
                      v-if="sdkTaskState.status === 'queued' || sdkTaskState.status === 'running'"
                      class="sdk-cancel-action"
                      :icon="Close"
                      :loading="sdkCancelBusy"
                      :disabled="sdkCancelBusy"
                      size="small"
                      plain
                      type="danger"
                      @click="cancelSdkTask"
                    >取消更新</el-button>
                  </div>
                </div>
                <p class="sdk-task-message">{{ sdkTaskState.message || sdkTaskStageLabel(sdkTaskState.stage) }}</p>
                <div v-if="sdkTaskState.current_package" class="sdk-task-context">
                  <span>当前包 <strong>{{ sdkTaskState.current_package }}</strong></span>
                  <span v-if="sdkTaskState.current_version">版本 <strong>{{ sdkTaskState.current_version }}</strong></span>
                  <span v-if="sdkTaskState.current_action">动作 <strong>{{ sdkActionLabel(sdkTaskState.current_action) }}</strong></span>
                </div>
                <div v-if="sdkHasDownloadProgress(sdkTaskState)" class="sdk-task-download">
                  <span>下载 <strong>{{ formatBytes(sdkTaskState.downloaded_bytes) }}</strong><template v-if="sdkTaskState.total_bytes !== null && sdkTaskState.total_bytes !== undefined"> / {{ formatBytes(sdkTaskState.total_bytes) }}</template><template v-else> / 总大小未知</template></span>
                  <span>速度 <strong>{{ formatSpeed(sdkTaskState.download_speed) }}</strong></span>
                </div>
                <el-progress
                  :percentage="sdkTaskState.progress || 0"
                  :indeterminate="sdkTaskIsIndeterminate(sdkTaskState)"
                  :duration="2"
                  :status="sdkTaskState.status === 'failed' ? 'exception' : sdkTaskState.status === 'succeeded' ? 'success' : undefined"
                />
                <div v-if="sdkTaskState.operations?.length" class="sdk-task-operations">
                  <div v-for="(operation, index) in sdkTaskState.operations" :key="`${operation.name}-${operation.action}-${index}`" class="sdk-task-operation">
                    <div class="sdk-task-operation-main">
                      <span class="sdk-task-operation-index">{{ index + 1 }}</span>
                      <span class="sdk-task-operation-name">{{ sdkOperationText(operation) }}</span>
                    </div>
                    <div class="sdk-task-operation-detail">
                      <small v-if="sdkHasDownloadProgress(operation)">下载 {{ formatBytes(operation.downloaded_bytes) }}<template v-if="operation.total_bytes !== null && operation.total_bytes !== undefined"> / {{ formatBytes(operation.total_bytes) }}</template><template v-else> / 总大小未知</template> · {{ formatSpeed(operation.download_speed) }}</small>
                      <small v-else>{{ operation.message || sdkTaskStageLabel(operation.stage) }}</small>
                      <el-tag :type="sdkTaskOperationType(operation)" effect="plain" size="small">{{ sdkTaskOperationStatusLabel(operation.status) }}</el-tag>
                    </div>
                  </div>
                </div>
                <p v-if="sdkTaskState.error" class="sdk-task-error">{{ sdkTaskState.error.message }}</p>
              </div>
              <el-alert v-if="sdkError" :title="sdkError" type="error" :closable="false" show-icon />
              <el-skeleton v-else-if="sdkLoading && !sdkState" :rows="5" animated />
              <el-empty v-else-if="!sdkState" description="当前 Env 没有可用 SDK 索引" />
              <template v-else>
                <el-alert v-if="sdkState.available === false" :title="sdkState.error || '当前 Env 没有可用 SDK 索引'" type="warning" :closable="false" show-icon />
                <el-empty v-if="sdkState.available === false" description="当前 Env 没有可用 SDK 索引" />
                <div class="sdk-list">
                  <div class="sdk-list-header" aria-hidden="true">
                    <span>工具链</span><span>状态</span><span>启用</span><span>版本</span><span>安装状态</span>
                  </div>
                  <article v-for="item in sdkState.packages" :key="item.name" class="sdk-list-row">
                    <div class="sdk-package-cell"><h2>{{ item.name }}</h2><p>{{ item.description }}</p></div>
                    <div class="sdk-status-cell"><el-tag :type="item.state === 'installed' ? 'success' : item.state === 'disabled' ? 'info' : 'warning'" effect="plain">{{ sdkStateLabel(item.state) }}</el-tag></div>
                    <div class="sdk-enable-cell">
                      <el-checkbox
                        :model-value="sdkSelection[item.name]?.enabled"
                        :disabled="sdkBusy"
                        @update:model-value="setSdkEnabled(item, $event)"
                      >启用</el-checkbox>
                    </div>
                    <div class="sdk-version-cell">
                      <el-select
                        :model-value="sdkSelection[item.name]?.version"
                        :disabled="!sdkSelection[item.name]?.enabled || sdkBusy"
                        placeholder="选择版本"
                        @update:model-value="setSdkVersion(item, $event)"
                      >
                        <el-option v-for="version in item.versions" :key="version.version" :label="version.version" :value="version.version" />
                      </el-select>
                    </div>
                    <div class="sdk-meta-cell"><span>期望 {{ item.expected_version || '未选择' }}</span><span>实际 {{ item.installed_version || '未安装' }}</span></div>
                  </article>
                </div>
                <div v-if="sdkPlanResult" class="sdk-plan">
                  <div class="sdk-plan-heading"><strong>变更预览</strong><span>{{ sdkPlanResult.operations.length ? `${sdkPlanResult.operations.length} 项操作` : '无需变更' }}</span></div>
                  <el-empty v-if="!sdkPlanResult.operations.length" :image-size="44" description="配置与已安装 SDK 一致" />
                  <div v-else class="sdk-operation-list">
                    <div v-for="operation in sdkPlanResult.operations" :key="`${operation.name}-${operation.action}`" class="sdk-operation">
                      <span>{{ sdkOperationText(operation) }}</span>
                      <el-tag :type="operation.action === 'remove' ? 'danger' : operation.action === 'switch' ? 'warning' : 'success'" effect="plain">{{ sdkActionLabel(operation.action) }}</el-tag>
                    </div>
                  </div>
                  <el-alert v-if="sdkPlanResult.remove_confirmation.length" title="应用变更时将要求再次确认删除目录" type="warning" :closable="false" show-icon />
                  <div class="sdk-plan-actions"><el-button :disabled="sdkBusy" @click="sdkPlanResult = null">取消</el-button><el-button class="sdk-primary-action sdk-action-button" type="primary" :loading="sdkBusy" :disabled="sdkBusy || !sdkPlanResult.operations.length" @click="applySdkPlan">应用更新</el-button></div>
                </div>
              </template>
            </el-tab-pane>
          </el-tabs>
        </section>

        <section v-show="currentView !== 'plugins' && currentView !== 'settings'" class="plugin-content">
          <div class="plugin-frame-stack">
            <iframe
              v-for="plugin in mountedFramePlugins"
              :key="plugin.id"
              :ref="(element) => setIframeElement(plugin.id, element)"
              v-show="currentView === plugin.id"
              class="plugin-frame"
              :title="plugin.name"
              :src="session?.plugin_assets?.[plugin.id]?.base || ''"
              sandbox="allow-scripts"
              @load="iframeLoaded(plugin.id)"
            ></iframe>
            <div v-if="activePlugin?.missing_required_permissions?.length" class="boundary-state">
              <WarningFilled /><h1>需要恢复权限</h1><p>{{ activePlugin.name }} 缺少运行所需的必需权限。</p>
              <div><el-button @click="go('plugins'); pluginTab = 'installed'">返回插件中心</el-button><el-button type="primary" :icon="Lock" @click="openManage(activePlugin)">管理权限</el-button></div>
            </div>
            <div v-else-if="activePlugin && iframeState === 'checking'" class="boundary-state compact-state">
              <el-icon class="is-loading"><Refresh /></el-icon><p>检查插件状态</p>
            </div>
            <div v-else-if="activePlugin && (iframeState === 'timeout' || iframeState === 'error')" class="boundary-state">
              <WarningFilled /><h1>插件页面未能加载</h1><p>{{ activePlugin.name }} 的故障未影响 Env WebUI 和其他插件。</p>
              <div><el-button @click="go('plugins'); pluginTab = 'installed'">返回插件中心</el-button><el-button :icon="Refresh" type="primary" @click="go(activePlugin.id, true)">重新加载</el-button></div>
            </div>
          </div>
        </section>
      </main>
    </div>

    <el-dialog v-model="toolchainEditorVisible" width="min(560px, calc(100vw - 28px))" :title="toolchainEditingName ? '编辑本地工具链' : '添加本地工具链'" align-center destroy-on-close @closed="resetToolchainEditor">
      <el-form label-position="top" @submit.prevent="saveToolchain">
        <el-form-item label="名称">
          <el-input v-model="toolchainForm.name" placeholder="例如 arm-none-eabi-gcc" maxlength="120" />
        </el-form-item>
        <el-form-item label="工具链路径">
          <el-input v-model="toolchainForm.path" placeholder="工具链 bin 目录或可执行文件所在目录" maxlength="2048" />
        </el-form-item>
        <el-form-item label="说明">
          <el-input v-model="toolchainForm.description" type="textarea" :rows="2" maxlength="240" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button :disabled="toolchainBusy" @click="closeToolchainEditor">取消</el-button>
        <el-button class="sdk-primary-action sdk-action-button" type="primary" :loading="toolchainBusy" :disabled="!toolchainForm.name.trim() || !toolchainForm.path.trim()" @click="saveToolchain">{{ toolchainEditingName ? '保存修改' : '保存配置' }}</el-button>
      </template>
    </el-dialog>

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

    <el-dialog v-model="marketDetailVisible" width="min(680px, calc(100vw - 28px))" :show-close="false" align-center destroy-on-close>
      <template #header>
        <div v-if="marketDetail" class="dialog-heading">
          <span class="plugin-icon"><component :is="iconFor(marketDetail)" /></span>
          <div><h2>{{ marketDetail.name }}</h2><p>{{ marketDetail.id }} · v{{ marketDetail.latest_version }}</p></div>
          <el-button text circle :icon="Close" aria-label="关闭详情" @click="marketDetailVisible = false" />
        </div>
      </template>
      <template v-if="marketDetail">
        <p class="dialog-description">{{ marketDetail.description }}</p>
        <div class="detail-section"><h3>提供的能力</h3>
          <div v-for="capability in marketDetail.capabilities || []" :key="capability" class="capability"><Platform /><span><strong>{{ capabilityLabel(capability) }}</strong></span></div>
          <div v-if="!(marketDetail.capabilities || []).length" class="capability"><InfoFilled /><span><strong>无可用入口</strong></span></div>
        </div>
        <div class="detail-section"><h3>当前环境</h3>
          <div class="capability"><Cpu /><span><strong>{{ marketDetail.compatible ? '当前环境可以安装' : '当前环境不能安装' }}</strong><small>{{ runtimeText(diagnosisOf(marketDetail)?.runtime) }}</small></span></div>
        </div>
        <div class="detail-section" v-if="blockingReasons(marketDetail).length"><h3>不能安装的原因</h3>
          <div v-for="reason in blockingReasons(marketDetail)" :key="reason.code" class="capability">
            <WarningFilled />
            <span><strong>{{ reasonText(reason) }}</strong><small>{{ reason.message }}</small></span>
          </div>
        </div>
        <div class="detail-section" v-if="diagnosisArtifacts(marketDetail).length"><h3>市场制品对照</h3>
          <div v-for="(artifact, index) in diagnosisArtifacts(marketDetail)" :key="`${artifact.version}-${index}`" class="capability">
            <component :is="artifact.compatible ? CircleCheck : WarningFilled" />
            <span>
              <strong>{{ artifact.filename || `v${artifact.version}` }} · {{ artifact.compatible ? '匹配' : '不匹配' }}</strong>
              <small>{{ artifact.summary }}</small>
            </span>
          </div>
        </div>
        <div class="detail-section" v-else-if="marketDetail.compatibility_message">
          <div class="capability"><Cpu /><span><strong>{{ marketDetail.compatible ? '将安装匹配制品' : '未解析到兼容制品' }}</strong><small>{{ marketDetail.compatibility_message }}</small></span></div>
        </div>
        <div class="detail-section" v-if="marketDetail.installed"><h3>本机版本</h3>
          <div class="capability"><Box /><span><strong>v{{ marketDetail.installed_version }}</strong><small>{{ marketDetail.enabled ? '已启用' : '已禁用' }}</small></span></div>
        </div>
      </template>
      <template #footer>
        <el-button @click="marketDetailVisible = false">关闭</el-button>
        <el-button
          v-if="canUninstallFromMarket(marketDetail)"
          :icon="Delete"
          type="danger"
          plain
          :loading="actionBusy"
          @click="confirmMarketUninstall(marketDetail)"
        >卸载</el-button>
        <el-button
          v-if="canInstallFromMarket(marketDetail) || canUpgradeFromMarket(marketDetail)"
          type="primary"
          :loading="actionBusy"
          @click="beginMarketInstall(marketDetail)"
        >{{ marketActionLabel(marketDetail) }}</el-button>
        <el-button
          v-else-if="marketDetail?.action === 'incompatible' && !marketDetail.installed"
          disabled
        >{{ marketActionLabel(marketDetail) }}</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="marketPrepareVisible" width="min(620px, calc(100vw - 28px))" :title="marketPrepare && installedPluginFor(marketPrepare) ? '更新在线插件' : '安装在线插件'" align-center :close-on-click-modal="!actionBusy">
      <p class="dialog-description">{{ marketPrepareStage }}</p>
      <el-alert
        v-if="marketPrepareError"
        :title="explainMarketError(marketPrepareError)"
        type="error"
        :closable="false"
        show-icon
      >
        <p>失败阶段：{{ stageLabels[marketPrepareError.stage] || marketPrepareError.stage }}</p>
        <p v-if="marketPrepareError.message">原始错误：{{ marketPrepareError.message }}</p>
        <p v-if="marketPrepareError.code">错误码：{{ marketPrepareError.code }}</p>
      </el-alert>
      <div v-if="marketPrepareError?.diagnosis" class="detail-section">
        <h3>诊断</h3>
        <div class="capability"><Cpu /><span><strong>当前环境</strong><small>{{ runtimeText(marketPrepareError.diagnosis.runtime) }}</small></span></div>
        <div v-for="reason in marketPrepareError.diagnosis.reasons || []" :key="reason.code" class="capability">
          <WarningFilled /><span><strong>{{ reasonText(reason) }}</strong><small>{{ reason.message }}</small></span>
        </div>
        <div v-for="(artifact, index) in marketPrepareError.diagnosis.artifacts || []" :key="`prepare-${artifact.version}-${index}`" class="capability">
          <component :is="artifact.compatible ? CircleCheck : WarningFilled" />
          <span><strong>{{ artifact.filename || `v${artifact.version}` }}</strong><small>{{ artifact.summary }}</small></span>
        </div>
      </div>
      <template v-if="marketPrepare">
        <div class="import-review">
          <strong>{{ marketPrepare.name }} · v{{ marketPrepare.version }}</strong>
          <span>{{ marketPrepare.id }}</span>
          <span>{{ compatibilityText(marketPrepare) }}</span>
        </div>
        <div class="permission-review compact-review">
          <div v-if="marketPrepare.webui"><Platform /><span><strong>WebUI 页面</strong><small>{{ marketPrepare.webui.entry }}</small></span></div>
          <div v-for="permission in marketPrepare.permissions" :key="permission.name"><Lock /><span><strong>{{ permissionLabels[permission.name] || permission.name }}</strong><small>{{ permission.reason }}</small></span></div>
        </div>
        <el-alert v-if="marketPrepare.signing_status === 'unsigned'" title="此包没有可验证的发布者签名" type="warning" :closable="false" show-icon />
        <el-checkbox v-if="marketPrepare.signing_status === 'unsigned'" v-model="marketUnsignedConsent" class="risk-consent">我已确认来源并接受未签名包风险</el-checkbox>
      </template>
      <template #footer>
        <el-button :disabled="actionBusy" @click="marketPrepareVisible = false">取消</el-button>
        <el-button
          type="primary"
          :loading="actionBusy"
          :disabled="!marketPrepare || marketPrepare.compatibility_issues.length || (marketPrepare.signing_status === 'unsigned' && !marketUnsignedConsent)"
          @click="confirmMarketInstall"
        >{{ marketPrepare && installedPluginFor(marketPrepare) ? '确认更新' : '确认安装' }}</el-button>
      </template>
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
