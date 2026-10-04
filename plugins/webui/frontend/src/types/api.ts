/** Shared contracts for the local Env WebUI API. */

export type PluginCapability = 'cli' | 'webui' | 'health_check' | string
export type PluginAction = 'install' | 'upgrade' | 'installed' | 'incompatible' | string
export type SigningStatus = 'signed' | 'unsigned' | string

export interface Permission {
  name: string
  reason: string
  required: boolean
}

export interface PluginCommand {
  name: string
  description?: string
}

export interface PluginWebUi {
  entry: string
  icon?: string | PluginIconAsset
  keep_alive?: boolean
  launch_requirements?: PluginLaunchRequirement
}

export interface PluginIconAsset {
  type: 'svg' | 'png'
  path: string
}

export type PluginLaunchRequirement =
  | { type: 'file' | 'directory'; pattern: string }
  | { all: PluginLaunchRequirement[] }
  | { any: PluginLaunchRequirement[] }
  | { not: PluginLaunchRequirement }

export interface PluginLaunchRequirementResult {
  satisfied: boolean
  message: string
  tree: PluginLaunchRequirementResultNode | null
}

export interface PluginLaunchRequirementResultNode {
  satisfied: boolean
  message: string
  type?: 'file' | 'directory'
  operator?: 'all' | 'any' | 'not'
  pattern?: string
  matches?: string[]
  children?: PluginLaunchRequirementResultNode[]
}

export interface PluginBackendContext {
  http_base: string
  websocket_base: string
}

export interface PluginAssetContext {
  base: string
  backend: PluginBackendContext | null
  icon_url?: string | null
}

export interface PluginHostBackendContext {
  httpBase: string
  websocketBase: string
}

export interface PluginHostContext {
  protocolVersion: number
  pluginId: string
  sdkVersion: string
  theme: 'light' | 'dark'
  language: string
  backend: PluginHostBackendContext | null
  features: string[]
}

export interface Compatibility {
  platforms?: string[]
  [key: string]: unknown
}

export interface EnvPlugin {
  id: string
  name: string
  version: string
  latest_version?: string
  description: string
  author: { name: string; [key: string]: unknown }
  enabled: boolean
  webui?: PluginWebUi | null
  commands: Array<string | PluginCommand>
  capabilities?: PluginCapability[]
  permissions: Permission[]
  granted_permissions: string[]
  missing_required_permissions?: string[]
  workspace_ready?: boolean
  launch_requirements_status?: PluginLaunchRequirementResult
  compatibility?: Compatibility
  compatibility_issues: string[]
  compatibility_message?: string
  signing_status: SigningStatus
  source_type?: string
  source_name?: string
  installed?: boolean
  installed_version?: string
  action?: PluginAction
  compatible?: boolean
  diagnosis?: MarketDiagnosis
  details?: Record<string, unknown>
  download_count?: number
  [key: string]: unknown
}

export interface MarketDiagnosisReason {
  code: string
  message?: string
  [key: string]: unknown
}

export interface MarketArtifact {
  version?: string
  filename?: string
  compatible?: boolean
  summary?: string
  [key: string]: unknown
}

export interface MarketDiagnosis {
  summary?: string
  reasons?: MarketDiagnosisReason[]
  artifacts?: MarketArtifact[]
  runtime?: RuntimeProfile
  [key: string]: unknown
}

export interface MarketCatalog {
  items: EnvPlugin[]
  total: number
  [key: string]: unknown
}

export interface MarketStatus {
  enabled: boolean
  url: string
  source: string
  reachable: boolean
  message?: string
  runtime?: RuntimeProfile
}

export interface RuntimeProfile {
  env: string
  python: string
  platform: string
  architecture: string
  implementation: string
  abi: string
  [key: string]: unknown
}

export interface Session {
  csrf_token: string
  frontend_sdk?: string
  plugin_assets?: Record<string, PluginAssetContext>
  market: {
    enabled: boolean
    url?: string
    source?: string
    [key: string]: unknown
  }
  [key: string]: unknown
}

export interface WorkspaceSnapshot {
  path: string
  files: { rtconfig: boolean; sconstruct: boolean; kconfig: boolean }
  build_available: boolean
  kconfig_available: boolean
  kconfig_plugin: EnvPlugin | null
  home_document: string | null
}

export interface WorkspaceDocument {
  path: string
  content: string
}

export interface NetworkConfig {
  proxy_mode: 'system' | 'direct' | 'custom'
  proxy_url: string
  no_proxy: string
  download_server: 'auto' | 'github' | 'gitee'
  pypi_mode: 'auto' | 'default' | 'aliyun' | 'custom'
  pypi_url: string
  timeout: number
}

export interface NetworkSnapshot {
  settings: NetworkConfig
  config_path: string
  configured: boolean
  pypi_overridden: boolean
}

export interface NetworkTestResult {
  target: string
  reachable: boolean
  status: number | null
  elapsed_ms: number
  message: string
}

export type BuildTaskStatus = 'queued' | 'running' | 'succeeded' | 'failed' | 'cancelled'
export type BuildOperation = 'build' | 'clean'

export interface BuildTask {
  task_id: string
  status: BuildTaskStatus
  progress: number
  stage: string
  message: string
  summary: string[]
  logs: string[]
  elf_files: Array<{ path: string; size: number; mtime: number }>
  returncode: number | null
  operation: BuildOperation
}

export interface PackageVersion {
  version: string
  [key: string]: unknown
}

export interface SdkPackage {
  name: string
  description?: string
  enabled: boolean
  expected_version?: string | null
  installed_version?: string | null
  versions?: PackageVersion[]
  state: string
  [key: string]: unknown
}

export interface SdkSnapshot {
  available: boolean
  platform: string
  packages_root: string
  index_root: string
  config_path: string
  revision: string | number
  config_revision: string | number
  packages: SdkPackage[]
  error?: string
  [key: string]: unknown
}

export interface SdkSelection {
  enabled: boolean
  version: string | null
}

export interface SdkRequestPackage {
  name: string
  enabled: boolean
  version: string | null
}

export interface SdkOperation {
  name: string
  action: string
  version?: string | null
  from_version?: string | null
  to_version?: string | null
  [key: string]: unknown
}

export interface SdkPlan {
  plan_id: string
  operations: SdkOperation[]
  remove_confirmation?: string[]
  [key: string]: unknown
}

export type SdkTaskStatus = 'queued' | 'running' | 'succeeded' | 'failed' | 'cancelled' | string

export interface SdkTaskOperation extends SdkOperation {
  status: string
  stage?: string
  message?: string
  downloaded_bytes?: number
  total_bytes?: number | null
  download_speed?: number
}

export interface SdkTask {
  task_id: string
  status: SdkTaskStatus
  stage: string
  message?: string
  progress?: number
  operation_index?: number
  operation_total?: number
  current_package?: string
  current_version?: string
  current_action?: string
  downloaded_bytes?: number
  total_bytes?: number | null
  download_speed?: number
  operations?: SdkTaskOperation[]
  snapshot?: SdkSnapshot
  error?: { code?: string; message?: string; [key: string]: unknown }
  [key: string]: unknown
}

export interface ToolchainEntry {
  name: string
  path: string
  description?: string
  [key: string]: unknown
}

export interface DetectedToolchain {
  id: string
  name: string
  path: string
  config_name?: string
  configured?: boolean
  [key: string]: unknown
}

export interface ToolchainSnapshot {
  platform: string
  config_path: string
  entries: ToolchainEntry[]
  detected?: DetectedToolchain[]
  [key: string]: unknown
}

export interface ToolchainForm {
  name: string
  path: string
  description: string
}

export interface ContextMenuSnapshot {
  available?: boolean
  platform?: string
  supported?: boolean
  installed?: boolean
  error?: string
  [key: string]: unknown
}

export interface UploadSummary extends EnvPlugin {
  path?: string
  upload_id: string
}

export interface MarketPrepareError {
  stage: string
  code?: string
  message: string
  details?: Record<string, unknown>
  diagnosis?: MarketDiagnosis
}

export interface DoctorResult {
  status: string
  plugins: Array<{ issues?: string[]; [key: string]: unknown }>
  [key: string]: unknown
}

export class ApiError extends Error {
  code: string
  status: number
  details?: Record<string, unknown>

  constructor(message: string, code: string, status: number, details?: Record<string, unknown>) {
    super(message)
    this.name = 'ApiError'
    this.code = code
    this.status = status
    this.details = details
  }
}
