import { computed, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api } from '../api'
import type { SdkOperation, SdkPlan, SdkRequestPackage, SdkSelection, SdkSnapshot, SdkTask } from '../types/api'

function selectionFromSnapshot(snapshot: SdkSnapshot): Record<string, SdkSelection> {
  return Object.fromEntries((snapshot.packages || []).map((item) => [item.name, {
    enabled: item.enabled,
    version: item.expected_version || item.versions?.[0]?.version || null,
  }]))
}

export function useSdk() {
  const sdkState = ref<SdkSnapshot | null>(null)
  const sdkSelection = ref<Record<string, SdkSelection>>({})
  const sdkLoading = ref(false)
  const sdkBusy = ref(false)
  const sdkCancelBusy = ref(false)
  const sdkError = ref('')
  const sdkPlanResult = ref<SdkPlan | null>(null)
  const sdkTaskState = ref<SdkTask | null>(null)

  const sdkDirty = computed(() => {
    if (!sdkState.value) return false
    return sdkState.value.packages.some((item) => {
      const selected = sdkSelection.value[item.name]
      if (!selected) return false
      const configChanged = selected.enabled !== item.enabled || (selected.enabled && selected.version !== item.expected_version)
      return configChanged || ['selected_not_installed', 'version_change', 'pending_remove'].includes(item.state)
    })
  })

  async function loadSdk(): Promise<void> {
    if (sdkBusy.value) return
    sdkLoading.value = true
    sdkError.value = ''
    try {
      const state = await api.sdk()
      sdkState.value = state
      sdkSelection.value = selectionFromSnapshot(state)
      sdkPlanResult.value = null
      sdkTaskState.value = null
    } catch (error) {
      sdkError.value = error instanceof Error ? error.message : String(error)
    } finally {
      sdkLoading.value = false
    }
  }

  function setSdkEnabled(item: SdkSnapshot['packages'][number], enabled: boolean): void {
    const selected = sdkSelection.value[item.name]
    if (!selected) return
    selected.enabled = enabled
    if (enabled && !selected.version) selected.version = item.versions?.[0]?.version || null
    sdkPlanResult.value = null
  }

  function setSdkVersion(item: SdkSnapshot['packages'][number], version: string): void {
    const selected = sdkSelection.value[item.name]
    if (!selected) return
    selected.version = version
    sdkPlanResult.value = null
  }

  function sdkRequestPackages(): SdkRequestPackage[] {
    return (sdkState.value?.packages || []).map((item) => {
      const selected = sdkSelection.value[item.name]
      return { name: item.name, enabled: Boolean(selected?.enabled), version: selected?.enabled ? selected.version : null }
    })
  }

  function sdkOperationText(operation: SdkOperation): string {
    if (operation.action === 'remove') return `${operation.name} · 移除 ${operation.version}`
    if (operation.action === 'switch') return `${operation.name} · ${operation.from_version} → ${operation.to_version}`
    if (operation.action === 'install') return `${operation.name} · 安装 ${operation.to_version}`
    if (operation.action === 'disable') return `${operation.name} · 禁用`
    return `${operation.name} · 启用 ${operation.version || ''}`
  }

  async function previewSdkPlan(): Promise<void> {
    if (!sdkState.value || sdkBusy.value) return
    sdkBusy.value = true
    try {
      sdkPlanResult.value = await api.sdkPlan(sdkRequestPackages())
      sdkTaskState.value = null
    } catch (error) {
      sdkPlanResult.value = null
      ElMessage.error(error instanceof Error ? error.message : String(error))
    } finally {
      sdkBusy.value = false
    }
  }

  async function applySdkPlan(): Promise<void> {
    if (!sdkPlanResult.value || sdkBusy.value) return
    const removals = sdkPlanResult.value.remove_confirmation || []
    if (removals.length) {
      try {
        await ElMessageBox.confirm(
          `本次操作将删除 ${removals.join('、')} 的已安装目录，是否继续？`,
          '确认删除 SDK 包',
          { type: 'warning', confirmButtonText: '确认删除', cancelButtonText: '取消' },
        )
      } catch {
        return
      }
    }
    sdkBusy.value = true
    sdkTaskState.value = null
    try {
      const task = await api.sdkApply(sdkPlanResult.value.plan_id, removals)
      sdkTaskState.value = task
      let current = task
      while (current.status === 'queued' || current.status === 'running') {
        await new Promise((resolve) => window.setTimeout(resolve, 180))
        current = await api.sdkTask(task.task_id)
        sdkTaskState.value = current
      }
      if (current.status === 'succeeded' && current.snapshot) {
        sdkState.value = current.snapshot
        sdkSelection.value = selectionFromSnapshot(current.snapshot)
        sdkPlanResult.value = null
        ElMessage.success('SDK 配置已更新')
      } else if (current.status === 'cancelled') {
        ElMessage.info('SDK 更新已取消，未应用变更')
      } else {
        sdkPlanResult.value = null
        ElMessage.error(current.error?.message || 'SDK 更新失败')
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error)
      if (sdkTaskState.value) {
        sdkTaskState.value = {
          ...sdkTaskState.value,
          status: 'failed',
          stage: 'failed',
          message: `无法读取 SDK 更新进度：${message}`,
          error: { code: 'task_poll_failed', message },
        }
      }
      ElMessage.error(message)
      if ((error as { code?: string })?.code === 'stateerror') await loadSdk()
    } finally {
      sdkBusy.value = false
    }
  }

  async function cancelSdkTask(): Promise<void> {
    const task = sdkTaskState.value
    if (!task || !['queued', 'running'].includes(task.status) || sdkCancelBusy.value) return
    sdkCancelBusy.value = true
    try {
      sdkTaskState.value = await api.sdkCancelTask(task.task_id)
    } catch (error) {
      ElMessage.error(error instanceof Error ? error.message : String(error))
    } finally {
      sdkCancelBusy.value = false
    }
  }

  return {
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
    sdkRequestPackages,
    sdkOperationText,
    previewSdkPlan,
    applySdkPlan,
    cancelSdkTask,
  }
}
