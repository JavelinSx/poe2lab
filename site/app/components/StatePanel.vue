<script setup lang="ts">
// An empty list, a missing page, an error: what happened and the next step (the actions in the slot).
defineProps<{ title: string; text?: string; icon?: string; code?: string; tone?: "bad" | "gold"; hint?: string }>();
</script>

<template>
  <div class="panel state">
    <span v-if="code" class="state-code">{{ code }}</span>
    <span v-else :class="['state-art', tone]"><Ic :name="icon ?? 'info'" /></span>
    <h2>{{ title }}</h2>
    <p v-if="text">{{ text }}</p>
    <slot />
    <span v-if="hint" class="hint">{{ hint }}</span>
  </div>
</template>
