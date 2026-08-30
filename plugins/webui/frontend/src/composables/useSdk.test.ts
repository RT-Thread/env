import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../api'
import type { SdkSnapshot } from '../types/api'
import { useSdk } from './useSdk'

vi.mock('../api', () => ({
  api: {
    sdk: vi.fn(),
    sdkApply: vi.fn(),
    sdkTask: vi.fn(),
  },
}))

vi.mock('element-plus', () => ({
  ElMessage: {
    error: vi.fn(),
    info: vi.fn(),
    success: vi.fn(),
  },
  ElMessageBox: { confirm: vi.fn() },
}))

const snapshot: SdkSnapshot = {
  available: true,
  platform: 'Linux',
  packages_root: '/tmp/packages',
  index_root: '/tmp/index',
  config_path: '/tmp/.config',
  revision: 'r1',
  config_revision: 'r1',
  packages: [],
}

describe('useSdk', () => {
  beforeEach(() => vi.clearAllMocks())

  it('reloads the snapshot after a stale plan state error', async () => {
    vi.mocked(api.sdkApply).mockRejectedValue(Object.assign(new Error('stale plan'), { code: 'stateerror' }))
    vi.mocked(api.sdk).mockResolvedValue(snapshot)

    const sdk = useSdk()
    sdk.sdkPlanResult.value = { plan_id: 'plan-1', operations: [] }

    await sdk.applySdkPlan()

    expect(api.sdk).toHaveBeenCalledTimes(1)
    expect(sdk.sdkState.value).toEqual(snapshot)
    expect(sdk.sdkBusy.value).toBe(false)
  })
})
