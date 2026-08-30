import type { Component } from 'vue'
import { Box } from '@element-plus/icons-vue'
import type {
  EnvPlugin,
  MarketArtifact,
  MarketDiagnosis,
  MarketDiagnosisReason,
  PluginCommand,
} from '../types/api'
import { iconMap, marketActionLabels } from '../constants'

export function iconFor(plugin?: Partial<EnvPlugin> | null): Component {
  return iconMap[plugin?.webui?.icon || ''] || (plugin?.commands?.length ? iconMap.tools : Box)
}

export function compatibilityText(plugin: Pick<EnvPlugin, 'compatibility_issues' | 'compatibility'>): string {
  if (plugin.compatibility_issues?.length) return plugin.compatibility_issues[0]
  const platforms = plugin.compatibility?.platforms || []
  return platforms.includes('any') ? 'Windows · Linux · macOS' : platforms.join(' · ')
}

export function commandNames(plugin: Partial<Pick<EnvPlugin, 'commands'>>): string[] {
  return (plugin.commands || []).map((command) => typeof command === 'string' ? command : command.name)
}

export function commandDescription(command: string | PluginCommand): string {
  return typeof command === 'string' ? '插件命令入口' : command.description || '插件命令入口'
}

export function capabilityLabel(name: string): string {
  return { cli: 'CLI', webui: 'WebUI', health_check: '健康检查' }[name] || name
}

export function marketActionLabel(item?: Partial<EnvPlugin> | null): string {
  return marketActionLabels[item?.action || ''] || '安装'
}

export function installedPluginFor(installed: EnvPlugin[], plugin?: Partial<EnvPlugin> | null): EnvPlugin | undefined {
  return installed.find((item) => item.id === plugin?.id)
}

export function canInstallFromMarket(plugin?: Partial<EnvPlugin> | null): boolean {
  return plugin?.action === 'install'
}

export function canUpgradeFromMarket(plugin?: Partial<EnvPlugin> | null): boolean {
  return Boolean(plugin?.installed && plugin.action === 'upgrade')
}

export function canUninstallFromMarket(plugin?: Partial<EnvPlugin> | null): boolean {
  return Boolean(plugin?.installed)
}

export function marketStateClass(item?: Partial<EnvPlugin> | null): string {
  if (item?.action === 'upgrade') return 'update'
  if (item?.action === 'installed') return 'open'
  if (item?.action === 'incompatible') return 'incompatible'
  return 'disabled'
}

export function marketStateLabel(item?: Partial<EnvPlugin> | null): string {
  if (item?.action === 'upgrade') return '可更新'
  if (item?.action === 'installed') return '已安装'
  if (item?.action === 'incompatible') return '不兼容'
  return `v${item?.latest_version || ''}`
}

export function diagnosisOf(plugin?: Partial<EnvPlugin> | null): MarketDiagnosis | null {
  return plugin?.diagnosis || (plugin?.details?.diagnosis as MarketDiagnosis | undefined) || null
}

export function diagnosisReasons(plugin?: Partial<EnvPlugin> | null): MarketDiagnosisReason[] {
  return diagnosisOf(plugin)?.reasons || []
}

export function blockingReasons(plugin?: Partial<EnvPlugin> | null): MarketDiagnosisReason[] {
  return diagnosisReasons(plugin).filter((reason) => reason.code !== 'already_latest')
}

export function diagnosisArtifacts(plugin?: Partial<EnvPlugin> | null): MarketArtifact[] {
  return diagnosisOf(plugin)?.artifacts || []
}
