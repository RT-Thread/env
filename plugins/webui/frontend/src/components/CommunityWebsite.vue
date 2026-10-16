<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { Refresh, TopRight } from '@element-plus/icons-vue'
import type { CommunityWebsite } from '../utils/community'

defineProps<{ website: CommunityWebsite }>()
const frameVersion = ref(0)
const state = ref<'loading' | 'ready' | 'timeout' | 'error'>('loading')
let loadTimer: number | undefined

function startLoading() {
  window.clearTimeout(loadTimer)
  state.value = 'loading'
  loadTimer = window.setTimeout(() => { state.value = 'timeout' }, 15_000)
}

function reload() {
  startLoading()
  frameVersion.value += 1
}

function loaded() {
  window.clearTimeout(loadTimer)
  state.value = 'ready'
}

function failed() {
  window.clearTimeout(loadTimer)
  state.value = 'error'
}

onMounted(startLoading)

onBeforeUnmount(() => {
  window.clearTimeout(loadTimer)
})
</script>

<template>
  <section class="community-view" :aria-label="website.title">
    <div class="community-frame-container" :aria-busy="state === 'loading'">
      <iframe
        :key="frameVersion"
        class="community-frame"
        :title="website.title"
        :src="website.url"
        sandbox="allow-scripts allow-same-origin allow-forms allow-popups allow-popups-to-escape-sandbox allow-storage-access-by-user-activation"
        referrerpolicy="strict-origin-when-cross-origin"
        @load="loaded"
        @error="failed"
      />
      <div v-if="state === 'loading'" class="community-loading" role="status">正在加载网页...</div>
        <div v-else-if="state === 'timeout' || state === 'error'" class="community-error" role="alert">
          <strong>{{ state === 'timeout' ? '网页加载超时' : '网页加载失败' }}</strong>
          <p>请检查网络连接，或在浏览器中打开网页。</p>
          <div class="community-error-actions">
            <el-button :icon="Refresh" @click="reload">重试</el-button>
            <el-button
              tag="a"
              :icon="TopRight"
              :href="website.url"
              target="_blank"
              rel="noopener noreferrer"
            >
              在浏览器中打开
            </el-button>
          </div>
        </div>
      </div>
  </section>
</template>
