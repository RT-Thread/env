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
  icon?: string
  keep_alive?: boolean
}

export interface PluginBackendContext {
  http_base: string
  websocket_base: string
}

export interface PluginAssetContext {
  base: string
  backend: PluginBackendContext | null
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
