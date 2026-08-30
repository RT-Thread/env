import type { MarketDiagnosisReason, RuntimeProfile, SdkTask, SdkTaskOperation } from '../types/api'
import { marketReasonLabels, sdkActionLabels, sdkStateLabels, sdkTaskOperationStatusLabels, sdkTaskStageLabels } from '../constants'

export function sdkStateLabel(state: string): string {
  return sdkStateLabels[state] || state
}

export function sdkActionLabel(action: string): string {
  return sdkActionLabels[action] || action
}

export function sdkTaskStageLabel(stage?: string): string {
  return sdkTaskStageLabels[stage || ''] || stage || '处理中'
}

export function sdkTaskOperationStatusLabel(status?: string): string {
  return sdkTaskOperationStatusLabels[status || ''] || status || '等待中'
}

export function sdkTaskOperationType(operation: { status?: string }): 'danger' | 'success' | 'info' | 'warning' {
  if (operation?.status === 'failed') return 'danger'
  if (operation?.status === 'succeeded') return 'success'
  if (operation?.status === 'skipped' || operation?.status === 'cancelled') return 'info'
  return 'warning'
}

export function sdkTaskIsIndeterminate(task?: SdkTask | null): boolean {
  return task?.status === 'running' && ['downloading', 'extracting'].includes(task.stage)
}

export function sdkHasDownloadProgress(task?: Pick<SdkTask, 'stage' | 'downloaded_bytes' | 'total_bytes'> | Pick<SdkTaskOperation, 'stage' | 'downloaded_bytes' | 'total_bytes'> | null): boolean {
  const downloadStage = ['downloading', 'downloaded', 'extracting', 'staged', 'completed', 'cancelled'].includes(task?.stage || '')
  return downloadStage && (Number.isFinite(task?.downloaded_bytes) || Number.isFinite(task?.total_bytes))
}

export function formatBytes(value?: number | null): string {
  if (!Number.isFinite(value) || (value as number) < 0) return '未知'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let amount = value as number
  let unit = 0
  while (amount >= 1024 && unit < units.length - 1) {
    amount /= 1024
    unit += 1
  }
  const precision = unit === 0 || amount >= 10 || Number.isInteger(amount) ? 0 : 1
  return `${amount.toFixed(precision)} ${units[unit]}`
}

export function formatSpeed(value?: number | null): string {
  if (!Number.isFinite(value) || (value as number) <= 0) return '计算中'
  return `${formatBytes(value)}/s`
}

export function sdkTaskTitle(task?: SdkTask | null): string {
  if (task?.status === 'failed') return '更新失败'
  if (task?.status === 'succeeded') return '更新完成'
  if (task?.status === 'cancelled') return '更新已取消'
  if (task?.status === 'queued') return '等待更新'
  return '正在更新'
}

export function runtimeText(runtime?: RuntimeProfile | null): string {
  if (!runtime) return ''
  return `Env ${runtime.env} · Python ${runtime.python} · ${runtime.platform}/${runtime.architecture} · ${runtime.implementation}/${runtime.abi}`
}

export function reasonText(reason?: MarketDiagnosisReason | null): string {
  return marketReasonLabels[reason?.code || ''] || reason?.message || ''
}

export function explainMarketError(error?: { code?: string; message?: string } | null): string {
  if (!error) return ''
  return marketReasonLabels[error.code || ''] || error.message || '操作失败'
}

export function requestedPluginId(): string {
  const value = new URLSearchParams(window.location.search).get('plugin')
  return value?.trim() || ''
}

export function syncViewUrl(view: string): void {
  const url = new URL(window.location.href)
  if (view !== 'plugins' && view !== 'settings') url.searchParams.set('plugin', view)
  else url.searchParams.delete('plugin')
  window.history.replaceState({}, '', `${url.pathname}${url.search}${url.hash}`)
}
