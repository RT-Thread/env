<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { Connection, Refresh, Check } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { api } from '../api'
import type { NetworkConfig, NetworkSnapshot, NetworkTestResult } from '../types/api'

const props = defineProps<{ marketEnabled: boolean }>()
const snapshot = ref<NetworkSnapshot | null>(null)
const form = ref<NetworkConfig | null>(null)
const loading = ref(false)
const saving = ref(false)
const testing = ref(false)
const error = ref('')
const target = ref('github')
const result = ref<NetworkTestResult | null>(null)
const dirty = computed(() => JSON.stringify(form.value) !== JSON.stringify(snapshot.value?.settings ?? null))
const validUrl = (value: string, proxy = false): boolean => {
  try {
    const url = new URL(value)
    return ['http:', 'https:'].includes(url.protocol) && Boolean(url.hostname)
      && !url.username && !url.password && !url.search && !url.hash
      && !/\s/.test(value) && (!proxy || url.pathname === '/')
  } catch { return false }
}
const valid = computed(() => Boolean(form.value && (
  form.value.proxy_mode !== 'custom' || validUrl(form.value.proxy_url, true)
) && (
  form.value.pypi_mode !== 'custom' || validUrl(form.value.pypi_url)
) && Number.isInteger(form.value.timeout) && form.value.timeout >= 1 && form.value.timeout <= 300))

async function load() {
  loading.value = true
  error.value = ''
  try {
    snapshot.value = await api.network()
    form.value = { ...snapshot.value.settings }
    result.value = null
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : String(cause)
  } finally { loading.value = false }
}

async function save() {
  if (!form.value || !valid.value) return
  saving.value = true
  error.value = ''
  try {
    snapshot.value = await api.saveNetwork({
      ...form.value,
      proxy_url: form.value.proxy_mode === 'custom' ? form.value.proxy_url : '',
      pypi_url: form.value.pypi_mode === 'custom' ? form.value.pypi_url : '',
    })
    form.value = { ...snapshot.value.settings }
    result.value = null
    ElMessage.success('网络设置已保存')
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : String(cause)
  } finally { saving.value = false }
}

async function testConnection() {
  if (dirty.value || !snapshot.value) return
  testing.value = true
  result.value = null
  error.value = ''
  try { result.value = await api.testNetwork(target.value) }
  catch (cause) { error.value = cause instanceof Error ? cause.message : String(cause) }
  finally { testing.value = false }
}

onMounted(load)
</script>

<template>
  <div class="network-settings">
    <div class="network-toolbar">
      <code v-if="snapshot">{{ snapshot.config_path }}</code>
      <el-button :icon="Refresh" :loading="loading" :disabled="saving || testing" @click="load">重新加载</el-button>
    </div>
    <el-alert v-if="error" :title="error" type="error" :closable="false" show-icon />
    <el-skeleton v-if="loading && !form" :rows="6" animated />
    <el-form v-if="form" :disabled="loading || saving || testing" label-position="top" class="network-form">
      <el-form-item label="代理模式">
        <el-segmented v-model="form.proxy_mode" :options="[
          { label: '系统代理', value: 'system' },
          { label: '直连', value: 'direct' },
          { label: '自定义代理', value: 'custom' },
        ]" aria-label="代理模式" />
      </el-form-item>
      <el-form-item v-if="form.proxy_mode === 'custom'" label="代理地址" :error="form.proxy_url && !validUrl(form.proxy_url, true) ? '请输入不含账号密码的 HTTP(S) 代理地址' : ''">
        <el-input v-model="form.proxy_url" placeholder="http://127.0.0.1:7890" aria-label="代理地址" />
      </el-form-item>
      <el-form-item v-if="form.proxy_mode !== 'direct'" label="不使用代理的主机">
        <el-input v-model="form.no_proxy" placeholder="localhost,127.0.0.1,::1,.example.com" aria-label="不使用代理的主机" />
      </el-form-item>
      <div class="network-form-grid">
        <el-form-item label="下载服务器">
          <el-select v-model="form.download_server" aria-label="下载服务器">
            <el-option label="自动" value="auto" />
            <el-option label="GitHub" value="github" />
            <el-option label="Gitee 镜像" value="gitee" />
          </el-select>
        </el-form-item>
        <el-form-item label="Python 包索引">
          <el-select v-model="form.pypi_mode" aria-label="Python 包索引">
            <el-option label="自动" value="auto" />
            <el-option label="pip 默认源" value="default" />
            <el-option label="阿里云镜像" value="aliyun" />
            <el-option label="自定义" value="custom" />
          </el-select>
        </el-form-item>
      </div>
      <el-form-item v-if="form.pypi_mode === 'custom'" label="Python 包索引地址" :error="form.pypi_url && !validUrl(form.pypi_url) ? '请输入不含账号密码的 HTTP(S) 索引地址' : ''">
        <el-input v-model="form.pypi_url" placeholder="https://pypi.org/simple/" aria-label="Python 包索引地址" />
      </el-form-item>
      <el-alert v-if="snapshot?.pypi_overridden" title="ENV_PYPI_INDEX_URL 环境变量正在覆盖 Python 包索引" type="warning" :closable="false" show-icon />
      <el-form-item label="请求超时（秒）">
        <el-input-number v-model="form.timeout" :min="1" :max="300" :step="1" aria-label="请求超时（秒）" />
      </el-form-item>
      <div class="network-save-actions">
        <el-button type="primary" :icon="Check" :loading="saving" :disabled="!valid || (!dirty && Boolean(snapshot?.configured)) || loading || testing" @click="save">保存网络设置</el-button>
        <span v-if="dirty" class="network-unsaved">未保存</span>
      </div>
    </el-form>
    <div v-if="snapshot" class="network-connection">
      <el-select v-model="target" aria-label="连接测试目标" :disabled="testing">
        <el-option label="GitHub" value="github" />
        <el-option label="Gitee" value="gitee" />
        <el-option label="Python 包索引" value="pypi" />
        <el-option v-if="props.marketEnabled" label="插件市场" value="market" />
      </el-select>
      <el-button :icon="Connection" :loading="testing" :disabled="dirty || loading || saving" @click="testConnection">测试连接</el-button>
      <el-tag v-if="result" :type="result.reachable ? 'success' : 'danger'">
        {{ result.reachable ? '连接成功' : '连接失败' }} · {{ result.elapsed_ms }} ms
      </el-tag>
      <span v-if="result" class="network-test-message">{{ result.message }}</span>
    </div>
  </div>
</template>

<style scoped>
.network-toolbar, .network-save-actions, .network-connection { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.network-toolbar { justify-content: space-between; margin-bottom: 20px; }
.network-toolbar code { min-width: 0; overflow-wrap: anywhere; font-size: 12px; color: var(--muted); }
.network-form { max-width: 640px; margin-top: 20px; }
.network-form-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 20px; }
.network-form :deep(.el-select), .network-form :deep(.el-segmented) { width: 100%; }
.network-form :deep(.el-alert) { margin-bottom: 20px; }
.network-unsaved, .network-test-message { color: var(--muted); font-size: 12px; overflow-wrap: anywhere; }
.network-connection { margin-top: 24px; padding-top: 24px; border-top: 1px solid var(--line); }
.network-connection > .el-select { width: 180px; max-width: 100%; }
@media (max-width: 520px) {
  .network-form-grid { grid-template-columns: minmax(0, 1fr); gap: 0; }
  .network-toolbar { align-items: flex-start; flex-direction: column; }
  .network-form :deep(.el-segmented) { font-size: 12px; }
}
</style>
