<script setup lang="ts">
// A list or a page that did not come: no connection (the design's "Сайт временно недоступен") or the site's error,
// with "Повторить".
const props = defineProps<{ error: unknown }>();
defineEmits<{ retry: [] }>();
const offline = computed(() => !apiStatus(props.error));
</script>

<template>
  <StatePanel v-if="offline" icon="cloud-off" title="Сайт временно недоступен" text="Билды никуда не пропали. Уже открытые в poe2lab билды работают и без сайта.">
    <div class="row"><button class="btn btn-primary" type="button" @click="$emit('retry')"><Ic name="refresh" />Повторить</button></div>
  </StatePanel>
  <StatePanel v-else icon="warn" tone="bad" title="Что-то сломалось" :text="apiError(error)">
    <div class="row"><button class="btn btn-primary" type="button" @click="$emit('retry')"><Ic name="refresh" />Повторить</button></div>
  </StatePanel>
</template>
