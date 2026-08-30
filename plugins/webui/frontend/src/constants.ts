import type { Component } from 'vue'
import {
  Box,
  Cpu,
  DataAnalysis,
  Lock,
  Tools,
} from '@element-plus/icons-vue'

export const permissionLabels: Record<string, string> = {
  'workspace.read': '读取工作区',
  'workspace.write': '读写工作区',
  'process.execute': '执行本机进程',
  'network.access': '访问网络',
  'credentials.use': '使用凭据',
  'device.serial': '访问串行设备',
}

export const iconMap: Record<string, Component> = {
  'chart-no-axes-combined': DataAnalysis,
  'shield-check': Lock,
  cpu: Cpu,
  tools: Tools,
}

export const stageLabels: Record<string, string> = {
  resolve: '解析兼容制品',
  download: '下载插件包',
  inspect: '本机检查插件包',
  install: '写入本机安装状态',
}

export const sdkStateLabels: Record<string, string> = {
  disabled: '未启用',
  selected_not_installed: '待安装',
  installed: '已安装',
  version_change: '待切换版本',
  pending_remove: '待移除',
  installing: '安装中',
  extracting: '展开中',
  failed: '失败',
  cancelled: '已取消',
}

export const sdkActionLabels: Record<string, string> = {
  install: '安装',
  switch: '切换版本',
  remove: '移除',
  disable: '禁用',
  enable: '启用',
  write_config: '写入配置',
  refresh: '刷新状态',
}

export const sdkTaskStageLabels: Record<string, string> = {
  queued: '等待开始',
  preparing: '准备操作',
  downloading: '下载中',
  downloaded: '下载完成',
  extracting: '展开中',
  staged: '已准备',
  writing_config: '写入配置',
  refreshing: '刷新状态',
  completed: '已完成',
  failed: '失败',
  cancelled: '已取消',
}

export const sdkTaskOperationStatusLabels: Record<string, string> = {
  pending: '等待中',
  running: '进行中',
  staged: '已准备',
  succeeded: '已完成',
  failed: '失败',
  skipped: '未执行',
  cancelled: '已取消',
}

export const marketReasonLabels: Record<string, string> = {
  yanked: '插件或版本已从市场撤回，不能再下载',
  incompatible: '当前环境没有可安装的制品',
  no_versions: '市场中没有已发布版本',
  already_latest: '本机已是当前环境可安装的最新版本',
  ok: '当前环境可以安装',
  checksum_mismatch: '下载文件校验失败，文件可能损坏或不完整',
  market_unreachable: '无法连接插件市场',
  payload_too_large: '插件包超过大小限制',
  market_invalid_response: '插件市场返回了无法解析的数据',
  market_redirect_denied: '插件市场重定向到了未配置的地址',
  invalid_package: '下载到的插件包无法通过本机检查',
  stateerror: '本机插件状态不允许这次安装或更新',
  compatibilityerror: '插件包与当前 Env / Python / 平台不兼容',
  packageerror: '插件包结构或完整性检查失败',
  usageerror: '安装请求无效',
}

export const marketActionLabels: Record<string, string> = {
  install: '安装',
  upgrade: '更新',
  installed: '已安装',
  incompatible: '当前环境无兼容制品',
}
