<script setup lang="ts">
import type { ToastMsg } from "~/composables/useToast";
const list = useToasts();
const run = (t: ToastMsg) => { t.action?.run(); list.value = list.value.filter((x) => x.id !== t.id); };
</script>

<template>
  <div class="toasts" aria-live="polite">
    <span v-for="t in list" :key="t.id" :class="['toast', { bad: t.bad }]"><Ic :name="t.bad ? 'warn' : 'check'" />{{ t.text }}
      <a v-if="t.action" href="#" @click.prevent="run(t)">{{ t.action.label }}</a></span>
  </div>
</template>
