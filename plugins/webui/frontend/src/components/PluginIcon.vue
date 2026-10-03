<script setup lang="ts">
import { computed } from 'vue'
import type { EnvPlugin, PluginAssetContext } from '../types/api'
import { iconFor } from '../utils/plugins'

const props = defineProps<{
  plugin?: Partial<EnvPlugin> | null
  asset?: PluginAssetContext | null
}>()

const plugin = computed(() => props.plugin)

const imageUrl = computed(() => {
  const icon = props.plugin?.webui?.icon
  return typeof icon === 'object' ? props.asset?.icon_url || '' : ''
})
</script>

<template>
  <img
    v-if="imageUrl"
    class="plugin-image-icon"
    :src="imageUrl"
    :alt="`${plugin?.name || '插件'}图标`"
    draggable="false"
  >
  <component v-else :is="iconFor(plugin)" />
</template>
